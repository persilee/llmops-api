from typing import Any, Literal

from langchain.messages import HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.agent.agents.base_agent import BaseAgent
from src.core.agent.entities.agent_entity import AgentState


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
        if history is None:
            history = []

        agent = self._build_graph()

        return agent.invoke(
            {
                "message": [HumanMessage(content=query)],
                "history": history,
                "long_term_memory": long_term_memory,
            },
        )

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
        pass

    def _llm_node(self, state: AgentState) -> AgentState:
        pass

    def _tools_node(self, state: AgentState) -> AgentState:
        pass

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
