from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity

DEFAULT_CODE = """
def main(params)
    return params
"""


class CodeNodeData(BaseNodeData):
    code: str = DEFAULT_CODE
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(default_factory=list)
