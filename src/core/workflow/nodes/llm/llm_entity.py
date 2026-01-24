from typing import Any

from pydantic import Field, field_validator

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity, VariableValueType
from src.entity.app_entity import DEFAULT_APP_CONFIG


class LLMNodeData(BaseNodeData):
    """LLM节点数据类，用于存储语言模型节点的配置信息"""

    prompt: str  # 提示词文本，用于指导语言模型生成内容
    language_model_config: dict[str, Any] = Field(
        # 默认配置工厂函数，使用默认应用配置中的模型配置
        default_factory=lambda: DEFAULT_APP_CONFIG["model_config"],
    )
    inputs: list[VariableEntity] = Field(
        default_factory=list,
    )  # 输入变量列表，默认为空列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [  # 默认输出配置工厂函数
            VariableEntity(
                name="output",
                value={"type": VariableValueType.GENERATED},
            ),  # 创建名为"output"的输出变量，类型为生成内容
        ],
    )

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, _value: list[VariableEntity]) -> list[VariableEntity]:
        """验证并标准化outputs字段

        Args:
            _value (list[VariableEntity]): 待验证的输出变量列表，\
                虽然传入但实际不会被使用

        Returns:
            list[VariableEntity]: 返回一个包含默认输出变量的列表
                - 固定返回一个名为"output"的变量
                - 变量类型为GENERATED，表示这是由模型生成的内容

        """
        return [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED}),
        ]
