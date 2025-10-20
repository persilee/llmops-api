from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ToolParamType(str, Enum):
    """工具参数类型枚举类，定义了工具支持的参数类型"""

    STRING = "string"  # 字符串类型
    NUMBER = "number"  # 数字类型
    BOOLEAN = "boolean"  # 布尔类型
    ARRAY = "array"  # 数组类型


class ToolParam(BaseModel):
    """工具参数模型类，用于定义工具的参数配置

    Attributes:
        name: 参数名称
        label: 参数显示名称
        type: 参数类型
        required: 是否为必填参数，默认为False
        default: 参数默认值
        min: 数值类型参数的最小值
        max: 数值类型参数的最大值
        options: 参数选项列表，用于枚举类型参数

    """

    name: str  # 参数名称
    label: str  # 参数显示名称
    type: ToolParamType  # 参数类型
    required: bool = False  # 是否为必填参数，默认为False
    default: Any | None = None  # 参数默认值
    min: float | None = None  # 数值类型参数的最小值
    max: float | None = None  # 数值类型参数的最大值
    options: list[dict[str, Any]] = Field(
        default_factory=list,
    )  # 参数选项列表，用于枚举类型参数


class ToolEntity(BaseModel):
    """工具实体类，用于定义工具的基本属性和参数。

    该类作为工具系统的核心数据结构，用于标准化工具的定义和配置。
    每个工具实例都需要包含名称、描述、标签等基本信息，以及工具所需的参数列表。

    Attributes:
        name: 工具名称，用于唯一标识一个工具
        description: 工具的详细描述信息，说明工具的功能和用途
        label: 工具的显示标签，用于UI展示
        params: 工具参数列表，定义工具所需的输入参数，默认为空列表

    Example:
        tool = ToolEntity(
            name="calculator",
            description="A simple calculator tool",
            label="计算器",
            params=[
                ToolParam(
                    name="numbers",
                    label="数字",
                    type=ToolParamType.ARRAY,
                    required=True
                )
            ]
        )

    """

    name: str  # 工具名称
    description: str  # 工具描述信息
    label: str  # 工具标签
    params: list[ToolParam] = Field(default_factory=list)  # 工具参数列表，默认为空列表
