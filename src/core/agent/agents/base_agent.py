from abc import ABC, abstractmethod
from typing import Any

from langchain.messages import AnyMessage

from src.core.agent.entities.agent_entity import AgentConfig


class BaseAgent(ABC):
    agent_config: AgentConfig

    def __init__(self, agent_config: AgentConfig) -> None:
        self.agent_config = agent_config

    @abstractmethod
    def run(
        self,
        query: str,
        history: list[AnyMessage] | None = None,
        long_term_memory: str = "",
    ) -> Any:
        error_msg = "Agent 智能体必须实现 run 方法"
        raise NotImplementedError(error_msg)
