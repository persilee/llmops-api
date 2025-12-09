import uuid
from abc import abstractmethod
from collections.abc import Iterator
from threading import Thread
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.load import Serializable
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from pydantic import PrivateAttr

from src.core.agent.agents.agent_queue_manager import AgentQueueManager
from src.core.agent.entities.agent_entity import AgentConfig, AgentState
from src.core.agent.entities.queue_entity import AgentResult, AgentThought
from src.exception.exception import FailException


class BaseAgent(Serializable, Runnable):
    """智能体抽象基类，定义所有智能体的基本接口。

    Attributes:
        llm (BaseLanguageModel): 语言模型实例，用于生成智能体的响应
        agent_config (AgentConfig): 智能体配置信息，包含用户ID和调用来源等信息
        _agent (CompiledStateGraph): 编译后的状态图，定义智能体的行为流程
        _agent_queue_manager (AgentQueueManager): 智能体队列管理器，
        用于处理异步任务和响应

    """

    llm: BaseLanguageModel
    agent_config: AgentConfig
    _agent: CompiledStateGraph = PrivateAttr(None)
    _agent_queue_manager: AgentQueueManager = PrivateAttr(None)

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        llm: BaseLanguageModel,
        agent_config: AgentConfig,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """初始化智能体实例。

        Args:
            llm (BaseLanguageModel): 语言模型实例
            agent_config (AgentConfig): 智能体配置信息
            *args: 可变参数
            **kwargs: 关键字参数

        """
        super().__init__(*args, llm=llm, agent_config=agent_config, **kwargs)
        self._agent = self._build_agent()
        self._agent_queue_manager = AgentQueueManager(
            user_id=agent_config.user_id,
            invoke_from=agent_config.invoke_from,
        )

    @abstractmethod
    def _build_agent(self) -> CompiledStateGraph:
        """构建智能体的状态图。

        Returns:
            CompiledStateGraph: 编译后的状态图，定义智能体的行为流程

        """
        error_msg = "_build_agent 方法必须被实现"
        raise NotImplementedError(error_msg)

    def invoke(
        self,
        agent_input: AgentState,
        config: RunnableConfig | None = None,
        **kwargs: Any | None,
    ) -> AgentResult:
        """同步执行智能体任务。

        Args:
            agent_input: 智能体输入状态，包含任务相关信息
            config: 可选的运行配置
            **kwargs: 其他可选参数

        Returns:
            AgentResult: 智能体执行结果

        """

    def stream(
        self,
        agent_input: AgentState,
        config: RunnableConfig | None = None,
        **kwargs: Any | None,
    ) -> Iterator[AgentThought]:
        """流式处理智能体响应。

        该方法通过创建新线程来执行智能体任务，实现非阻塞的异步处理。
        使用队列管理器来监听和收集任务执行过程中的思考步骤，实现流式输出。

        Args:
            agent_input: 智能体输入状态，包含任务相关信息
            config: 可选的运行配置
            **kwargs: 其他可选参数

        Returns:
            Iterator[AgentThought]: 返回智能体思考过程的迭代器，可以实时获取执行状态

        Raises:
            FailException: 当智能体未初始化时抛出异常

        """
        # 检查智能体是否已初始化
        if not self._agent:
            error_msg = "智能体未初始化"
            raise FailException(error_msg)

        # 设置agent_input的默认值
        # 如果未提供task_id，则生成一个新的UUID
        agent_input["task_id"] = agent_input.get("task_id", uuid.uuid4())
        # 如果未提供历史记录，则初始化为空列表
        agent_input["history"] = agent_input.get("history", [])
        # 如果未提供迭代计数，则初始化为0
        agent_input["iteration_count"] = agent_input.get("iteration_count", 0)

        # 创建并启动一个新线程来执行智能体任务
        # 使用线程可以避免阻塞主线程，实现异步处理
        # 线程将执行智能体的状态图，并将结果通过队列管理器传递
        thread = Thread(
            target=self._agent.invoke,
            args=(agent_input,),
        )
        thread.start()

        # 通过队列管理器监听任务ID对应的响应
        # 使用yield from实现流式输出，实时返回智能体的思考过程
        yield from self._agent_queue_manager.listen(agent_input["task_id"])

    @property
    def agent_queue_manager(self) -> AgentQueueManager:
        """获取智能体队列管理器实例。

        Returns:
            AgentQueueManager: 智能体队列管理器实例，用于管理智能体的任务队列和响应流。

        """
        return self._agent_queue_manager
