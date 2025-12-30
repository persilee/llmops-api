from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity


class StartNodeData(BaseNodeData):
    """开始节点数据类。

    用于存储工作流开始节点的输入变量配置。
    继承自BaseNodeEntity基类。

    Attributes:
        inputs (list[VariableEntity]): 输入变量列表，默认为空列表

    """

    inputs: list[VariableEntity] = Field(default_factory=list)
