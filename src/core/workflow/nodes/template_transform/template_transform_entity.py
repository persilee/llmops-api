from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class TemplateTransformNodeData(BaseNodeData):
    """模板转换节点数据类

    用于定义模板转换节点的数据结构，包含模板字符串、输入变量和输出变量配置。
    该节点主要用于根据模板和输入变量生成输出结果。

    Attributes:
        template (str): 模板字符串，用于定义转换的模板格式
        inputs (list[VariableEntity]): 输入变量列表，包含模板中需要替换的变量
        outputs (list[VariableEntity]): 输出变量列表，
        默认包含一个名为"output"的生成类型变量

    """

    template: str = ""  # 模板字符串，定义转换的模板格式
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED}),
        ],
    )  # 输出变量列表，默认包含一个生成类型的输出变量
