from typing import Any

from pydantic import Field

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import VariableEntity, VariableValueType
from src.entity.app_entity import DEFAULT_APP_CONFIG


class LLMNodeData(BaseNodeData):
    """LLM节点数据类，用于存储语言模型节点的配置信息"""

    prompt: str  # 提示词文本，用于指导语言模型生成内容
    language_model_config: dict[str, Any] = Field(
        # 字段别名，用于序列化/反序列化
        alias="model_config",
        # 默认配置工厂函数，使用默认应用配置中的模型配置
        default_factory=lambda: DEFAULT_APP_CONFIG["model_config"],
    )
    inputs: list[VariableEntity] = Field(
        default_factory=list,
    )  # 输入变量列表，默认为空列表
    outputs: list[VariableEntity] = Field(
        exclude=True,  # 在序列化时排除此字段
        default_factory=lambda: [  # 默认输出配置工厂函数
            VariableEntity(
                name="output",
                value={"type": VariableValueType.GENERATED},
            ),  # 创建名为"output"的输出变量，类型为生成内容
        ],
    )
