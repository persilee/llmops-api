from abc import ABC

from langchain_core.runnables import RunnableSerializable

from src.core.workflow.entities.node_entity import BaseNodeData


class BaseNode(RunnableSerializable, ABC):
    """工作流基础节点类，所有工作流节点的基类。

    继承自RunnableSerializable和ABC，提供节点的基本功能。

    Attributes:
        node_data (BaseNodeData): 节点的数据对象，包含节点的基本信息和配置

    """

    node_data: BaseNodeData
