from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity


class StartNodeData(BaseNodeData):
    inputs: list[VariableEntity] = Field(default_factory=list)
