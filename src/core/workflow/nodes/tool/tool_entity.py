from typing import Any, Literal

from pydantic import Field, field_validator

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class ToolNodeData(BaseNodeData):
    """工具节点数据类，用于定义工作流中工具节点的配置信息。

    该类包含了工具节点的所有必要配置信息，包括工具类型、提供者信息、工具ID、
    参数设置以及输入输出变量的定义。

    Attributes:
        tool_type (Literal["builtin_tool", "api_tool", ""]): 工具类型，\
            可以是内置工具、API工具或空字符串
        provider_id (str): 工具提供者的唯一标识符
        tool_id (str): 工具的唯一标识符
        params (dict[str, Any]): 工具的配置参数字典，默认为空字典
        inputs (list[VariableEntity]): 输入变量列表，用于定义工具所需的输入参数，\
            默认为空列表
        outputs (list[VariableEntity]): 输出变量列表，定义工具的输出字段，\
            默认包含一个名为"text"的输出变量

    """

    tool_type: Literal["builtin_tool", "api_tool", ""] = Field(alias="type")  # 工具类型
    provider_id: str  # 工具提供者id
    tool_id: str  # 工具id
    params: dict[str, Any] = Field(default_factory=dict)  # 内置工具设置参数
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ],
    )  # 输出字段列表信息

    @classmethod
    @field_validator("outputs", mode="before")
    def validate_outputs(cls, _outputs: list[VariableEntity]) -> list[VariableEntity]:
        """验证并标准化工具节点的输出字段配置

        Args:
            _outputs (list[VariableEntity]): 原始的输出字段列表，
            参数名前缀下划线表示该参数在方法中未被使用

        Returns:
            list[VariableEntity]: 标准化后的输出字段列表，\
                始终包含一个名为"text"的默认输出变量

        Note:
            无论输入的_outputs是什么，该方法都会返回一个包含默认文本输出的列表
            确保工具节点始终有一个标准的文本输出字段

        """
        return [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ]
