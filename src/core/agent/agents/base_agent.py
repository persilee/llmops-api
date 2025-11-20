from abc import ABC, abstractmethod
from collections.abc import Generator

from langchain.messages import AnyMessage

from src.core.agent.agents.agent_queue_manager import AgentQueueManager
from src.core.agent.entities.agent_entity import AgentConfig
from src.core.agent.entities.queue_entity import AgentThought


class BaseAgent(ABC):
    """智能体抽象基类，定义所有智能体的基本接口。

    Attributes:
        agent_config (AgentConfig): 智能体配置信息
        agent_queue_manager (AgentQueueManager): 智能体队列管理器

    """

    agent_config: AgentConfig
    agent_queue_manager: AgentQueueManager

    def __init__(
        self,
        agent_config: AgentConfig,
        agent_queue_manager: AgentQueueManager,
    ) -> None:
        """初始化智能体实例。

        Args:
            agent_config (AgentConfig): 智能体配置信息
            agent_queue_manager (AgentQueueManager): 智能体队列管理器

        """
        self.agent_config = agent_config
        self.agent_queue_manager = agent_queue_manager

    @abstractmethod
    def run(
        self,
        query: str,
        history: list[AnyMessage] | None = None,
        long_term_memory: str = "",
    ) -> Generator[AgentThought, None, None]:
        """执行智能体的主要功能。

        Args:
            query (str): 用户输入的查询文本
            history (list[AnyMessage] | None): 历史对话消息列表，可选
            long_term_memory (str): 长期记忆信息，默认为空字符串

        Returns:
            Any: 智能体的执行结果

        Raises:
            NotImplementedError: 如果子类未实现此方法

        """
        error_msg = "Agent 智能体必须实现 run 方法"
        raise NotImplementedError(error_msg)
