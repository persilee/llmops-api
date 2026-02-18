from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity

DEFAULT_CODE = """
def main(params)
    return params
"""


class CodeNodeData(BaseNodeData):
    """代码节点数据类

    用于存储代码节点的相关数据，包括要执行的代码、输入变量和输出变量。

    Attributes:
        code (str): 要执行的代码内容，默认为DEFAULT_CODE
        inputs (list[VariableEntity]): 输入变量列表，用于定义代码的输入参数
        outputs (list[VariableEntity]): 输出变量列表，用于定义代码的输出结果

    """

    code: str = DEFAULT_CODE
    language: str = "python"
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(default_factory=list)
