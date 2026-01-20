import json
import logging
import re
import time
import uuid

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    messages_to_dict,
)
from langchain_core.tools import render_text_description_and_args

from src.core.agent.entities.agent_entity import (
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    MAX_ITERATION_RESPONSE,
    REACT_AGENT_SYSTEM_PROMPT_TEMPLATE,
    AgentState,
)
from src.core.agent.entities.queue_entity import AgentThought, QueueEvent
from src.core.llm_model.entities.model_entity import ModelFeature
from src.exception import FailException

from .function_call_agent import FunctionCallAgent

logger = logging.getLogger(__name__)
MIN_JSON_PREFIX_LENGTH = 7


class ReACTAgent(FunctionCallAgent):
    """基于ReACT推理的智能体，继承FunctionCallAgent，并重写long_term_memory_node和llm_node两个节点"""

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """重写长期记忆召回节点，使用prompt实现工具调用及规范数据生成"""
        # 1.判断是否支持工具调用，如果支持工具调用，
        # 则可以直接使用工具智能体的长期记忆召回节点
        if ModelFeature.TOOL_CALL in self.llm.features:
            return super()._long_term_memory_recall_node(state)

        # 2.根据传递的智能体配置判断是否需要召回长期记忆
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                    observation=long_term_memory,
                ),
            )

        # 3.检测是否支持AGENT_THOUGHT，如果不支持，则使用没有工具描述的prompt
        if ModelFeature.AGENT_THOUGHT not in self.llm.features:
            preset_messages = [
                SystemMessage(
                    AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                        preset_prompt=self.agent_config.preset_prompt,
                        long_term_memory=long_term_memory,
                    ),
                ),
            ]
        else:
            # 4.支持智能体推理，则使用REACT_AGENT_SYSTEM_PROMPT_TEMPLATE并添加工具描述
            preset_messages = [
                SystemMessage(
                    REACT_AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                        preset_prompt=self.agent_config.preset_prompt,
                        long_term_memory=long_term_memory,
                        tool_description=render_text_description_and_args(
                            self.agent_config.tools,
                        ),
                    ),
                ),
            ]

        # 5.将短期历史消息添加到消息列表中
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 6.校验历史消息是不是复数形式，
            # 也就是[人类消息, AI消息, 人类消息, AI消息, ...]
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(
                    state["task_id"],
                    "智能体历史消息列表格式错误",
                )
                logger.exception(
                    (
                        "智能体历史消息列表格式错误,",
                        "len(history)=%(len_history)d, history=%(history)s",
                    ),
                    {
                        "len_history": len(history),
                        "history": json.dumps(messages_to_dict(history)),
                    },
                )
                error_msg = "智能体历史消息列表格式错误"
                raise FailException(error_msg)
            # 7.拼接历史消息
            preset_messages.extend(history)

        # 8.拼接当前用户的提问消息
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 9.处理预设消息，将预设消息添加到用户消息前，
        # 先去删除用户的原始消息，然后补充一个新的代替
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """处理LLM响应的核心节点方法。

        该方法负责：
        1. 检查LLM是否支持工具调用，如果支持则使用父类实现
        2. 检查迭代次数是否超过限制
        3. 流式处理LLM响应，区分message和thought两种类型
        4. 处理token统计信息
        5. 根据响应类型进行相应的处理和状态更新

        Args:
            state (AgentState): 当前智能体的状态，包含消息历史、迭代次数等信息

        Returns:
            AgentState: 更新后的智能体状态，包含新的消息和统计信息

        """
        # 检查LLM是否支持工具调用功能，如果支持则直接使用父类的实现
        if ModelFeature.TOOL_CALL in self.llm.features:
            return super()._llm_node(state)

        # 检查当前迭代次数是否超过最大限制，如果超过则返回最大迭代响应
        if state["iteration_count"] > self.agent_config.max_iteration_count:
            return self._handle_max_iterations(state)

        # 初始化必要的变量
        id = uuid.uuid4()  # 生成唯一的消息ID
        start_at = time.perf_counter()  # 记录开始时间用于计算延迟
        gathered = None  # 用于累积LLM的响应内容
        is_first_chunk = True  # 标记是否是第一个数据块
        generation_type = ""  # 记录生成内容的类型（message或thought）

        # 流式处理LLM响应
        for chunk in self.llm.stream(state["messages"]):
            # 处理第一个数据块
            if is_first_chunk:
                gathered = chunk
                is_first_chunk = False
            else:
                # 累积后续数据块
                gathered += chunk

            # 如果已确定是message类型，则处理消息生成
            if generation_type == "message":
                self._handle_message_generation(
                    state,
                    chunk,
                    id,
                    start_at,
                )

            # 当累积的内容足够长且还未确定类型时，判断生成类型
            if (
                not generation_type
                and len(gathered.content.strip()) >= MIN_JSON_PREFIX_LENGTH
            ):
                generation_type = self._determine_generation_type(
                    gathered,
                    state,
                    id,
                    start_at,
                )

        # 计算token使用统计信息
        stats = self._calculate_token_stats(state, gathered)

        # 如果是thought类型，尝试处理思维生成
        if generation_type == "thought":
            try:
                return self._handle_thought_generation(
                    state,
                    gathered,
                    id,
                    stats,
                    start_at,
                )
            except (json.JSONDecodeError, ValueError) as _:
                # 如果解析失败，降级为message类型处理
                generation_type = "message"
                # 发布消息事件到队列
                self.agent_queue_manager.publish(
                    state["task_id"],
                    AgentThought(
                        id=id,
                        task_id=state["task_id"],
                        event=QueueEvent.AGENT_MESSAGE,
                        thought=gathered.content,
                        message=messages_to_dict(state["messages"]),
                        answer=gathered.content,
                        latency=(time.perf_counter() - start_at),
                    ),
                )

        # 处理消息结束并返回最终状态
        return self._handle_message_end(state, gathered, id, stats, start_at)

    def _handle_message_end(self, state, gathered, thought_id, stats, start_at) -> dict:
        """处理消息结束事件，发布相关事件到队列并返回更新后的状态。

        Args:
            state (AgentState): 当前代理状态，包含任务ID、消息列表和迭代次数等信息
            gathered: 收集到的消息内容
            thought_id (str): 思维ID，用于标识当前思维过程
            stats: 统计信息对象，包含token使用统计和价格信息
            start_at: 消息开始处理的时间戳

        Returns:
            dict: 更新后的状态，包含新的消息列表和递增的迭代次数

        该方法执行以下操作：
        1. 发布消息结束事件到队列，包含完整的消息信息和统计数据
        2. 发布代理结束事件到队列，标记任务完成
        3. 返回更新后的状态，包含新的消息和递增的迭代次数

        """
        # 发布消息结束事件到队列，包含完整的消息信息和统计数据
        self.agent_queue_manager.publish(
            state["task_id"],  # 任务ID
            AgentThought(
                id=thought_id,  # 思维ID
                task_id=state["task_id"],  # 任务ID
                event=QueueEvent.AGENT_MESSAGE,  # 事件类型：代理消息
                thought="",  # 思维内容
                # 消息相关字段
                message=messages_to_dict(state["messages"]),  # 将消息列表转换为字典格式
                message_token_count=stats["input_token_count"],  # 输入token数量
                message_unit_price=stats["input_price"],  # 输入token单价
                message_price_unit=stats["unit"],  # 价格单位
                # 答案相关字段
                answer="",  # 答案内容
                answer_token_count=stats["output_token_count"],  # 输出token数量
                answer_unit_price=stats["output_price"],  # 输出token单价
                answer_price_unit=stats["unit"],  # 价格单位
                # Agent推理统计相关
                total_token_count=stats["total_token_count"],  # 总token数量
                total_price=stats["total_price"],  # 总价格
                latency=(time.perf_counter() - start_at),  # 延迟时间（秒）
            ),
        )
        # 发布代理结束事件到队列，标记任务完成
        self.agent_queue_manager.publish(
            state["task_id"],  # 任务ID
            AgentThought(
                id=uuid.uuid4(),  # 生成唯一的事件ID
                task_id=state["task_id"],  # 任务ID
                event=QueueEvent.AGENT_END,  # 事件类型：代理结束
            ),
        )

        # 返回更新后的状态，包含新的消息和递增的迭代次数
        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}

    def _handle_thought_generation(
        self,
        state,
        gathered,
        thought_id,
        stats,
        start_at,
    ) -> dict:
        """处理思维生成的方法。该方法解析AI生成的思维内容，提取工具调用信息，并发布相应的事件。

        Args:
            state (AgentState): 当前智能体状态，包含任务ID、消息列表等信息
            gathered: 收集到的AI响应内容，包含思维信息
            thought_id: 思维的唯一标识符
            stats: 统计信息，包含token使用量、价格等数据
            start_at: 任务开始时间

        Returns:
            dict: 包含更新后的消息列表和迭代计数的字典
                - messages: 包含工具调用信息的AIMessage列表
                - iteration_count: 递增后的迭代计数

        Raises:
            json.JSONDecodeError: 当解析JSON内容失败时抛出
            IndexError: 当正则匹配失败时抛出

        Note:
            JSON中应包含name和args字段用于工具调用

        """
        # 使用正则解析信息，如果失败则当成普通消息返回
        pattern = r"^```json(.*?)```$"
        matches = re.findall(pattern, gathered.content, re.DOTALL)
        match_json = json.loads(matches[0])
        tool_calls = [
            {
                "id": str(uuid.uuid4()),
                "type": "tool_call",
                "name": match_json.get("name", ""),
                "args": match_json.get("args", {}),
            },
        ]
        self.agent_queue_manager.publish(
            state["task_id"],
            AgentThought(
                id=thought_id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_THOUGHT,
                thought=json.dumps(gathered.content),
                # 消息相关字段
                message=messages_to_dict(state["messages"]),
                message_token_count=stats["input_token_count"],
                message_unit_price=stats["input_price"],
                message_price_unit=stats["unit"],
                # 答案相关字段
                answer="",
                answer_token_count=stats["output_token_count"],
                answer_unit_price=stats["output_price"],
                answer_price_unit=stats["unit"],
                # Agent推理统计相关
                total_token_count=stats["total_token_count"],
                total_price=stats["total_price"],
                latency=(time.perf_counter() - start_at),
            ),
        )
        return {
            "messages": [AIMessage(content="", tool_calls=tool_calls)],
            "iteration_count": state["iteration_count"] + 1,
        }

    def _determine_generation_type(
        self,
        gathered,
        state,
        thought_id,
        start_at,
    ) -> str:
        """确定LLM生成内容的类型。

        则认为是思维类型；否则认为是普通消息类型。对于普通消息类型，会发布一个消息事件。

        Args:
            gathered: 包含生成内容的对象，需要包含content属性
            state: 当前智能体状态字典，包含task_id和messages等信息
            thought_id: 思维ID，用于事件追踪
            start_at: 开始时间戳，用于计算延迟

        Returns:
            str: 返回生成内容的类型，"thought"表示思维类型，"message"表示普通消息类型

        """
        if gathered.content.strip().startswith("```json"):
            generation_type = "thought"
        else:
            generation_type = "message"
            # 添加发布事件，避免前几个字符遗漏
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=thought_id,
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE,
                    thought=gathered.content,
                    message=messages_to_dict(state["messages"]),
                    answer=gathered.content,
                    latency=(time.perf_counter() - start_at),
                ),
            )

        return generation_type

    def _handle_max_iterations(self, state: AgentState) -> dict:
        """处理代理达到最大迭代次数时的响应。

        当代理的迭代次数超过最大限制时，此方法会被调用。它会：
        1. 发布一个包含最大迭代响应消息的AgentThought事件
        2. 发布一个代理结束事件
        3. 返回包含最大迭代响应消息的状态更新

        Args:
            state (AgentState): 当前代理状态，包含task_id和messages等信息

        Returns:
            dict: 更新后的状态字典，包含新的AI消息列表

        """
        self.agent_queue_manager.publish(
            state["task_id"],
            AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE,
                thought=MAX_ITERATION_RESPONSE,
                message=messages_to_dict(state["messages"]),
                answer=MAX_ITERATION_RESPONSE,
                latency=0,
            ),
        )
        self.agent_queue_manager.publish(
            state["task_id"],
            AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_END,
            ),
        )
        return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)]}

    def _handle_message_generation(
        self,
        state: AgentState,
        chunk,
        message_id,
        start_at,
    ) -> None:
        """处理消息生成的方法。

        Args:
            state (AgentState): 当前智能体状态，包含任务ID和消息历史等信息
            chunk: LLM生成的消息块，包含消息内容
            message_id: 消息的唯一标识符
            start_at: 消息生成开始的时间戳，用于计算延迟

        Returns:
            None: 该方法不返回任何值，直接将处理后的消息发布到队列

        功能说明：
            1. 获取智能体的审查配置
            2. 如果启用了审查功能，对消息内容中的关键词进行过滤替换
            3. 将处理后的消息发布到队列中，包含完整的消息信息和统计数据

        """
        review_config = self.agent_config.review_config
        content = chunk.content
        if review_config["enable"] and review_config["outputs_config"]["enable"]:
            for keyword in review_config["keywords"]:
                content = re.sub(
                    re.escape(keyword),
                    "**",
                    content,
                    flags=re.IGNORECASE,
                )

        self.agent_queue_manager.publish(
            state["task_id"],
            AgentThought(
                id=message_id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE,
                thought=content,
                message=messages_to_dict(state["messages"]),
                answer=content,
                latency=(time.perf_counter() - start_at),
            ),
        )

    def _calculate_token_stats(self, state: AgentState, gathered) -> None:
        """计算token使用统计信息

        Args:
            state (AgentState): 当前智能体状态，包含消息列表
            gathered: 收集到的LLM响应内容

        Returns:
            dict: 包含以下键值的字典:
                - input_token_count: 输入token数量
                - output_token_count: 输出token数量
                - total_token_count: 总token数量
                - total_price: 总价格
                - input_price: 输入token单价
                - output_price: 输出token单价
                - unit: 价格单位

        """
        input_token_count = self.llm.get_num_tokens_from_messages(state["messages"])
        output_token_count = self.llm.get_num_tokens_from_messages([gathered])
        input_price, output_price, unit = self.llm.get_pricing()
        total_token_count = input_token_count + output_token_count
        total_price = (
            input_token_count * input_price + output_token_count * output_price
        ) * unit
        return {
            "input_token_count": input_token_count,
            "output_token_count": output_token_count,
            "total_token_count": total_token_count,
            "total_price": total_price,
            "input_price": input_price,
            "output_price": output_price,
            "unit": unit,
        }

    def _tools_node(self, state: AgentState) -> AgentState:
        """重写工具节点，处理工具节点的`AI工具调用参数消息`与`工具消息转人类消息`"""
        # 1.调用父类的工具节点执行并获取结果
        super_agent_state = super()._tools_node(state)

        # 2.移除原始的AI工具调用参数消息，并创建新的ai消息
        tool_call_message = state["messages"][-1]
        remove_tool_call_message = RemoveMessage(id=tool_call_message.id)

        # 3.提取工具调用的第1条消息还原原始AI消息(ReACTAgent一次最多只有一个工具调用)
        tool_call_json = [
            {
                "name": tool_call_message.tool_calls[0].get("name", ""),
                "args": tool_call_message.tool_calls[0].get("args", {}),
            },
        ]
        ai_message = AIMessage(content=f"```json\n{json.dumps(tool_call_json)}\n```")

        # 4.将ToolMessage转换成HumanMessage，提升LLM的兼容性
        tool_messages = super_agent_state["messages"]
        content = ""
        for tool_message in tool_messages:
            content += f"工具: {tool_message.name}\n执行结果:{tool_message.content}\n==========\n\n"  # noqa: E501
        human_message = HumanMessage(content=content)

        # 5.返回最终消息
        return {"messages": [remove_tool_call_message, ai_message, human_message]}
