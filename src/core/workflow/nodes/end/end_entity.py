from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity


class EndNodeData(BaseNodeData):
    outputs: list[VariableEntity] = Field(default_factory=list)
