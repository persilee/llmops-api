from abc import ABC

from langchain_core.runnables import RunnableSerializable

from src.core.workflow.entities.node_entity import BaseNodeData


class BaseNode(RunnableSerializable, ABC):
    node_data: BaseNodeData
