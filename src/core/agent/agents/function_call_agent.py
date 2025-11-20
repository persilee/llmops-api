import json
from typing import Any, Literal

from langchain.messages import HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.agent.agents.base_agent import BaseAgent
from src.core.agent.entities.agent_entity import (
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    AgentState,
)
from src.exception.exception import FailException


class FunctionCallAgent(BaseAgent):
    def run(self, query, history=None, long_term_memory="") -> dict[str, Any] | Any:
        """运行FunctionCallAgent并返回结果。

        Args:
            query (str): 用户输入的查询内容
            history (list, optional): 对话历史记录，默认为None
            long_term_memory (str, optional): 长期记忆内容，默认为空字符串

        Returns:
            dict[str, Any] | Any: agent的执行结果，可能包含字典或其他类型的返回值

        """
        # 如果没有提供历史记录，初始化为空列表
        if history is None:
            history = []

        # 构建状态图实例，包含所有节点和边的配置
        agent = self._build_graph()

        # 准备agent的输入参数
        # 包含用户消息、历史记录和长期记忆
        input_data = {
            "message": [HumanMessage(content=query)],
            "history": history,
            "long_term_memory": long_term_memory,
        }

        # 调用agent执行任务
        # agent会根据状态图的配置依次处理各个节点
        return agent.invoke(input_data)

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
        1. 获取配置的大语言模型实例
        2. 检查并绑定可用工具到LLM实例
        3. 使用流式方式处理LLM响应
        4. 收集并返回完整的响应消息

        """
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

        # 初始化变量用于收集流式响应
        gathered = None
        is_first_chunk = True
        # 使用流式方式处理LLM响应
        for chunk in llm.stream(state["messages"]):
            if is_first_chunk:
                # 第一个响应块直接赋值
                gathered = chunk
                is_first_chunk = False
            else:
                # 后续响应块累加到gathered中
                gathered += chunk

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
        # 创建工具名称到工具对象的映射字典，方便后续通过名称快速查找对应的工具
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}

        # 从状态中获取最后一条消息，并提取其中的工具调用请求列表
        tool_calls = state["messages"][-1].tool_calls

        # 初始化消息列表，用于存储工具执行的结果
        messages = []
        # 遍历所有工具调用请求
        for tool_call in tool_calls:
            # 根据工具调用请求中的名称获取对应的工具对象
            tool = tools_by_name[tool_call["name"]]
            # 调用工具并传入参数，获取执行结果
            tool_result = tool.invoke(tool_call["args"])
            # 将工具执行结果封装成ToolMessage对象
            messages.append(
                ToolMessage(
                    # 设置工具调用ID，用于关联请求和响应
                    tool_call_id=tool_call["id"],
                    # 将工具执行结果转换为JSON字符串格式
                    content=json.dumps(tool_result),
                    # 设置工具名称
                    name=tool_call["name"],
                ),
            )

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
