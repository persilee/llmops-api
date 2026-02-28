from uuid import UUID

from pydantic import Field, field_validator

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableType,
    VariableValueType,
)
from src.exception import FailException


class IterationNodeData(BaseNodeData):
    """迭代节点数据"""

    workflow_ids: list[UUID]  # 需要迭代的工作流id
    inputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(
                name="inputs",
                type=VariableType.LIST_STRING,
                value={"type": VariableValueType.LITERAL, "content": []},
            ),
        ],
    )  # 输入变量列表
    outputs: list[VariableEntity] = Field(default_factory=list)

    @field_validator("workflow_ids")
    @classmethod
    def validate_workflow_ids(cls, value: list[UUID]) -> list[UUID]:
        """校验迭代的工作流数量是否小于等于1"""
        if len(value) > 1:
            error_msg = "迭代节点只能绑定一个工作流"
            raise FailException(error_msg)
        return value

    @field_validator("inputs")
    @classmethod
    def validate_inputs(cls, value: list[VariableEntity]) -> list[VariableEntity]:
        """校验输入变量是否正确"""
        # 1.判断是否一个输入变量，如果不是则抛出错误
        if len(value) != 1:
            error_msg = "迭代节点输入变量信息错误"
            raise FailException(error_msg)

        # 2.判断输入变量类型及字段是否出错
        iteration_inputs = value[0]
        allow_types = [
            VariableType.LIST_STRING,
            VariableType.LIST_INT,
            VariableType.LIST_FLOAT,
            VariableType.LIST_BOOLEAN,
        ]
        if (
            iteration_inputs.name != "inputs"
            or iteration_inputs.type not in allow_types
            or iteration_inputs.required is False
        ):
            error_msg = "迭代节点输入变量名字/类型/必填属性出错"
            raise FailException(error_msg)

        return value

    @field_validator("outputs")
    @classmethod
    def validate_outputs(cls, _value: list[VariableEntity]) -> list[VariableEntity]:
        """固定节点的输出为列表型字符串，该节点会将工作流中的所有结果迭代存储到该列表中"""
        return [
            VariableEntity(name="outputs", value={"type": VariableValueType.GENERATED}),
        ]
