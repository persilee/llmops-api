from enum import Enum

from pydantic import Field, HttpUrl, field_validator

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableType,
    VariableValueType,
)
from src.exception.exception import ValidateErrorException


class HttpRequestMethod(str, Enum):
    """Http请求方法类型枚举"""

    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


class HttpRequestInputType(str, Enum):
    """Http请求输入变量类型"""

    PARAMS = "params"  # query参数
    HEADERS = "headers"  # header请求头
    BODY = "body"  # body参数


class HttpRequestNodeData(BaseNodeData):
    """HTTP请求节点的数据模型类，用于存储HTTP请求相关的配置信息。

    Attributes:
        url (HttpUrl | None): 请求的URL地址，可以为空
        method (HttpRequestMethod): HTTP请求方法，默认为GET
        inputs (list[VariableEntity]): 输入变量列表，包含请求所需的参数、头部等信息
        outputs (list[VariableEntity]): 输出变量列表，包含请求的响应结果，
        默认包含状态码和响应文本

    """

    url: HttpUrl | None = None  # 请求URL地址
    method: HttpRequestMethod = HttpRequestMethod.GET  # API请求方法
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ],
    )

    @classmethod
    @field_validator("url", mode="before")
    def validate_url(cls, url: HttpUrl | None) -> HttpUrl | None:
        """验证并处理HTTP请求的URL字段

        Args:
            url (HttpUrl | None): 待验证的URL对象，可能为None或空字符串

        Returns:
            HttpUrl | None: 如果输入为空字符串则返回None，否则返回原始URL对象

        Note:
            该验证器在字段验证之前运行(pre=True)，并且总是运行(always=True)

        """
        return url if url != "" else None

    @classmethod
    @field_validator("outputs", mode="before")
    def validate_outputs(cls, _outputs: list[VariableEntity]) -> list[VariableEntity]:
        """验证并设置HTTP请求节点的输出变量

        Args:
            _outputs: 原始输出变量列表（实际上会被忽略）

        Returns:
            list[VariableEntity]: 固定的输出变量列表，包含：
                - status_code: HTTP状态码，整数类型
                - text: 响应文本内容

        Note:
            无论输入什么，都会返回固定的输出变量配置

        """
        return [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ]

    @classmethod
    @field_validator("inputs")
    def validate_inputs(cls, inputs: list[VariableEntity]) -> list[VariableEntity]:
        """校验输入列表数据"""
        # 1.校验判断输入变量列表中的类型信息
        for input in inputs:
            if input.meta.get("type") not in HttpRequestInputType.__members__.values():
                error_msg = "Http请求参数类型错误"
                raise ValidateErrorException(error_msg)

        # 2.返回校验后的数据
        return inputs
