import json
import time
import uuid
from collections.abc import Generator
from threading import Thread
from typing import Literal

from langchain.messages import HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.messages import messages_to_dict
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.agent.agents.base_agent import BaseAgent
from src.core.agent.entities.agent_entity import (
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    DATASET_RETRIEVAL_TOOL_NAME,
    AgentState,
)
from src.core.agent.entities.queue_entity import AgentThought, QueueEvent
from src.exception.exception import FailException


class FunctionCallAgent(BaseAgent):
    """一个支持函数调用的智能代理类。

    该类实现了一个基于状态图的智能代理系统，能够处理用户查询、管理对话历史、
    调用工具函数，并支持长期记忆功能。代理通过状态图的方式组织执行流程，
    包含长期记忆召回、大语言模型处理和工具调用等主要节点。

    主要功能：
    1. 处理用户查询并生成响应
    2. 管理对话历史记录
    3. 支持长期记忆功能
    4. 集成工具调用能力
    5. 提供流式响应处理

    状态图执行流程：
    - long_term_memory_recall: 处理长期记忆和消息预处理
    - llm: 大语言模型处理节点，支持工具绑定
    - tools: 工具调用执行节点

    Attributes:
        agent_config: 代理配置对象，包含LLM配置、工具列表等
        agent_queue_manager: 队列管理器，用于处理事件发布和监听

    Methods:
        run: 执行代理的主要逻辑，处理用户查询
        _build_graph: 构建并编译状态图
        _long_term_memory_recall_node: 处理长期记忆召回和消息预处理
        _llm_node: 处理大语言模型节点的逻辑
        _tools_node: 执行工具调用的节点方法
        _tools_condition: 判断是否需要调用工具的条件函数

    """

    def run(
        self,
        query,
        history=None,
        long_term_memory="",
    ) -> Generator[AgentThought, None, None]:
        """执行FunctionCallAgent的主要逻辑，处理用户查询并返回生成器形式的响应。

        Args:
            query (str): 用户输入的查询内容
            history (list, optional): 历史对话记录，默认为None，会被初始化为空列表
            long_term_memory (str, optional): 长期记忆内容，默认为空字符串

        Returns:
            Generator[AgentThought, None, None]: 生成器对象，
            用于异步产生agent的思考过程和结果

        Raises:
            FailException: 当agent执行过程中发生错误时抛出

        """
        # 初始化历史记录和状态图实例
        if history is None:
            history = []

        # 创建状态图实例
        agent = self._build_graph()

        # 创建并启动新线程来异步执行agent
        thread = Thread(
            target=agent.invoke,
            args=(
                {
                    "messages": [HumanMessage(content=query)],
                    "history": history,
                    "long_term_memory": long_term_memory,
                },
            ),
        )
        thread.start()

        # 监听并返回agent的执行结果
        yield from self.agent_queue_manager.listen()

    def _build_graph(self) -> CompiledStateGraph:
        """构建并编译状态图。

        创建一个包含以下节点的状态图：
        1. long_term_memory_recall: 长期记忆召回节点
        2. llm: 大语言模型节点
        3. tools: 工具调用节点

        状态图的执行流程：
        - 从long_term_memory_recall节点开始
        - 执行完long_term_memory_recall后进入llm节点
        - llm节点根据条件决定是否调用tools节点
        - tools节点执行完成后返回llm节点

        Returns:
            CompiledStateGraph: 编译完成的状态图

        """
        # 创建状态图实例
        graph = StateGraph(AgentState)

        # 添加三个主要节点
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        # 设置图的入口点
        graph.set_entry_point("long_term_memory_recall")
        # 添加从长期记忆召回到大语言模型的边
        graph.add_edge("long_term_memory_recall", "llm")
        # 添加从大语言模型的条件边，根据条件决定是否调用工具
        graph.add_conditional_edges("llm", self._tools_condition)
        # 添加从工具调用返回到大语言模型的边
        graph.add_edge("tools", "llm")

        # 编译并返回状态图
        return graph.compile()

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """处理长期记忆召回和消息预处理的节点函数。

        该方法负责：
        1. 获取并处理长期记忆内容
        2. 构建包含系统提示、历史消息和当前用户消息的消息列表
        3. 验证历史消息的格式正确性
        4. 返回更新后的消息状态

        Args:
            state (AgentState): 包含当前对话状态的字典，包括：
                - long_term_memory: 长期记忆内容
                - history: 历史消息列表
                - messages: 当前消息列表

        Returns:
            AgentState: 更新后的状态字典，包含：
                - messages: 处理后的消息列表，移除了原始用户消息并添加了预设消息

        Raises:
            FailException: 当历史消息格式错误时抛出异常

        """
        # 初始化长期记忆字符串
        long_term_memory = ""
        # 检查是否启用长期记忆功能
        if self.agent_config.enable_long_term_memory:
            # 从状态中获取长期记忆内容
            long_term_memory = state["long_term_memory"]

            # 发布长期记忆召回事件到队列管理器
            self.agent_queue_manager.publish(
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=self.agent_queue_manager.task_id,
                    event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                    observation=long_term_memory,
                ),
            )

        # 创建预设消息列表，包含系统提示
        preset_messages = [
            SystemMessage(
                # 使用模板格式化系统提示，包含预设提示和长期记忆
                AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                    preset_prompt=self.agent_config.preset_prompt,
                    long_term_memory=long_term_memory,
                ),
            ),
        ]

        # 获取历史消息
        history = state["history"]
        # 检查历史消息是否为非空列表
        if isinstance(history, list) and len(history) > 0:
            # 验证历史消息数量是否为偶数（成对的消息）
            if len(history) % 2 != 0:
                # 如果历史消息格式错误，抛出异常
                error_msg = "历史消息格式错误，请检查历史消息的格式。"
                raise FailException(error_msg)

            # 将历史消息添加到预设消息列表中
            preset_messages.append(history)

        # 获取最后一条用户消息
        human_message = state["messages"][-1]
        # 将用户消息转换为HumanMessage并添加到预设消息列表
        preset_messages.append(HumanMessage(human_message.content))

        # 返回新的消息状态：
        # 1. 移除原始用户消息
        # 2. 添加所有预设消息（系统提示、历史消息、新的用户消息）
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """处理大语言模型节点的逻辑，包括工具绑定和流式响应处理。

        Args:
            state (AgentState): 当前代理状态，包含消息列表等信息

        Returns:
            AgentState: 更新后的代理状态，包含大语言模型的完整响应消息

        该方法执行以下步骤：
        1. 初始化响应追踪变量（id、开始时间）
        2. 获取配置的大语言模型实例
        3. 检查并绑定可用工具到LLM实例
        4. 初始化流式响应处理变量
        5. 处理流式响应，区分工具调用和普通消息
        6. 根据响应类型发布相应的事件
        7. 返回包含完整响应的状态

        """
        # 初始化响应追踪变量
        id = uuid.uuid4()
        start_at = time.perf_counter()

        # 获取配置的大语言模型实例
        llm = self.agent_config.llm

        # 检查LLM是否支持工具绑定，并且配置中有可用的工具
        if (
            hasattr(llm, "bind_tools")  # 检查是否有bind_tools属性
            and callable(llm.bind_tools)  # 确保bind_tools是可调用的
            and len(self.agent_config.tools) > 0  # 确保有可用的工具
        ):
            # 将工具绑定到LLM实例上，使其能够调用这些工具
            llm = llm.bind_tools(self.agent_config.tools)

        # 初始化流式响应处理变量
        gathered = None  # 用于收集完整的响应
        is_first_chunk = True  # 标记是否为第一个响应块
        generation_type = ""  # 响应类型：thought（工具调用）或message（普通消息）

        # 处理流式响应
        for chunk in llm.stream(state["messages"]):
            if is_first_chunk:
                # 第一个响应块直接赋值
                gathered = chunk
                is_first_chunk = False
            else:
                # 后续响应块累加到gathered中
                gathered += chunk

            # 确定响应类型
            if not generation_type:
                if chunk.tool_calls:
                    generation_type = "thought"
                elif chunk.content:
                    generation_type = "message"

            # 根据响应类型发布相应的事件
            if generation_type == "message":
                self.agent_queue_manager.publish(
                    AgentThought(
                        id=id,
                        task_id=self.agent_queue_manager.task_id,
                        event=QueueEvent.AGENT_MESSAGE,
                        thought=chunk.content,
                        message=messages_to_dict(state["messages"]),
                        answer=chunk.content,
                        latency=(time.perf_counter() - start_at),
                    ),
                )

        # 处理工具调用类型响应的最终事件发布
        if generation_type == "thought":
            self.agent_queue_manager.publish(
                AgentThought(
                    id=id,
                    task_id=self.agent_queue_manager.task_id,
                    event=QueueEvent.AGENT_THOUGHT,
                    message=messages_to_dict(state["messages"]),
                    latency=(time.perf_counter() - start_at),
                ),
            )
        elif generation_type == "message":
            # 普通消息类型响应完成后停止监听
            self.agent_queue_manager.stop_listen()

        # 返回包含完整响应消息的状态字典
        return {"messages": [gathered]}

    def _tools_node(self, state: AgentState) -> AgentState:
        """执行工具调用的节点方法。

        该方法负责处理AI模型生成的工具调用请求，执行相应的工具并将结果封装成消息返回。
        具体步骤包括：
        1. 创建工具名称到工具对象的映射字典
        2. 从状态中获取工具调用请求列表
        3. 遍历并执行每个工具调用
        4. 将执行结果封装成ToolMessage对象列表

        Args:
            state (AgentState): 当前代理状态，包含消息列表等信息

        Returns:
            AgentState: 更新后的代理状态，包含工具执行结果的消息

        """
        # 创建工具名称到工具对象的映射字典，用于快速查找和调用指定工具
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}

        # 从状态中获取最后一条消息，并提取其中的工具调用请求列表
        # 最后一条消息应该是由LLM生成的，包含需要执行的工具调用信息
        tool_calls = state["messages"][-1].tool_calls

        # 初始化消息列表，用于存储每个工具调用的执行结果
        messages = []
        # 遍历所有工具调用请求，逐个执行并收集结果
        for tool_call in tool_calls:
            # 为每个工具调用生成唯一标识符，用于追踪和日志记录
            id = uuid.uuid4()
            # 记录工具调用开始时间，用于计算执行耗时
            start_at = time.perf_counter()
            # 根据工具调用请求中的名称获取对应的工具对象
            # 如果工具不存在，这里会抛出KeyError异常
            tool = tools_by_name[tool_call["name"]]
            # 调用工具并传入参数，获取执行结果
            # tool.invoke可能会抛出异常，需要由调用方处理
            tool_result = tool.invoke(tool_call["args"])
            # 将工具执行结果封装成ToolMessage对象，包含：
            # - tool_call_id: 关联原始工具调用请求
            # - content: 工具执行结果的JSON字符串
            # - name: 工具名称
            messages.append(
                ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                ),
            )

            # 根据工具类型选择不同的事件类型
            # dataset_retrieval工具使用专门的事件类型，其他工具使用通用事件类型
            event = (
                QueueEvent.AGENT_ACTION
                if tool_call["name"] != DATASET_RETRIEVAL_TOOL_NAME
                else QueueEvent.DATASET_RETRIEVAL
            )

            # 发布工具执行事件，包含以下信息：
            # - id: 事件唯一标识符
            # - task_id: 任务ID，用于关联同一任务的所有事件
            # - event: 事件类型
            # - observation: 工具执行结果
            # - tool: 工具名称
            # - tool_input: 工具输入参数
            # - latency: 工具执行耗时
            self.agent_queue_manager.publish(
                AgentThought(
                    id=id,
                    task_id=self.agent_queue_manager.task_id,
                    event=event,
                    observation=json.dumps(tool_result),
                    tool=tool_call["name"],
                    tool_input=tool_call["args"],
                    latency=(time.perf_counter() - start_at),
                ),
            )

        # 返回包含所有工具执行结果的新状态
        # 这些消息将被添加到消息列表中，供LLM节点处理
        return {"messages": messages}

    @classmethod
    def _tools_condition(cls, state: AgentState) -> Literal["tools", "__end__"]:
        """判断是否需要调用工具的条件函数。

        Args:
            state (AgentState): 当前状态，包含消息列表等信息

        Returns:
            Literal["tools", "__end__"]: 如果需要调用工具返回"tools"，
            否则返回"__end__"表示结束

        该函数检查最后一条AI消息是否包含工具调用请求：
        - 如果消息包含tool_calls属性且不为空，返回"tools"表示需要调用工具
        - 否则返回END表示流程结束

        """
        # 从状态中获取消息列表
        messages = state["messages"]
        # 获取最后一条消息（AI的回复）
        ai_message = messages[-1]

        # 检查AI消息是否包含工具调用请求
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            # 如果有工具调用请求，返回"tools"以触发工具调用节点
            return "tools"

        # 如果没有工具调用请求，返回END结束流程
        return END
