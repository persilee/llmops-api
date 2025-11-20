from abc import ABC, abstractmethod
from typing import Any

from langchain.messages import AnyMessage

from src.core.agent.entities.agent_entity import AgentConfig


class BaseAgent(ABC):
    """智能体抽象基类，定义所有智能体的基本接口。

    Attributes:
        agent_config (AgentConfig): 智能体配置信息

    """

    agent_config: AgentConfig

    def __init__(self, agent_config: AgentConfig) -> None:
        """初始化智能体实例。

        Args:
            agent_config (AgentConfig): 智能体配置信息

        """
        self.agent_config = agent_config

    @abstractmethod
    def run(
        self,
        query: str,
        history: list[AnyMessage] | None = None,
        long_term_memory: str = "",
    ) -> Any:
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
