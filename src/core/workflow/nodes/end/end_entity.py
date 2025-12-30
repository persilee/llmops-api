from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity


class EndNodeData(BaseNodeData):
    """结束节点数据类，用于存储工作流结束节点的输出变量信息。

    Attributes:
        outputs (list[VariableEntity]): 输出变量列表，存储该结束节点的所有输出变量

    """

    outputs: list[VariableEntity] = Field(default_factory=list)
