from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, ValidationError
from wtforms.validators import URL, DataRequired, Length, Optional

from pkg.paginator.paginator import PaginatorReq
from src.model.api_tool import ApiTool, ApiToolProvider
from src.schemas.schema import ListField


class ValidateOpenAPISchemaReq(FlaskForm):
    """OpenAPI Schema验证请求表单类

    用于验证和接收OpenAPI Schema字符串的表单

    属性:
        openapi_schema (StringField): OpenAPI Schema字符串字段
            - 必填字段
            - 用于接收OpenAPI格式的API文档字符串
    """

    openapi_schema = StringField(
        "openapi_schema",
        validators=[
            DataRequired(message="openapi_schema 字符串不能为空"),
        ],
    )


class CreateApiToolReq(FlaskForm):
    """创建API工具请求表单类

    用于验证和接收创建API工具所需的表单数据

    属性:
        name (StringField): 工具名称字段
            - 必填字段
            - 长度限制在1-30个字符之间
        icon (StringField): 工具图标URL字段
            - 必填字段
            - 必须是有效的URL格式
        openapi_schema (StringField): OpenAPI Schema字符串字段
            - 必填字段
            - 用于接收OpenAPI格式的API文档字符串
        headers (ListField): HTTP请求头字段
            - 可选字段
            - 必须是包含key和value的字典列表
    """

    name = StringField(
        "name",
        validators=[
            DataRequired(message="工具提供者的名字不能为空"),
            Length(min=1, max=30, message="工具提供者的名字长度应在1到30个字符之间"),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired(message="工具图标不能为空"),
            URL(message="工具图标必须是一个有效的URL"),
        ],
    )
    openapi_schema = StringField(
        "openapi_schema",
        validators=[DataRequired(message="openapi_schema不能为空")],
    )
    headers = ListField("headers")

    @classmethod
    def validate_headers(cls, _, field) -> None:
        """验证headers字段格式

        确保headers字段是一个字典列表，且每个字典都包含key和value字段

        Args:
            _: 表单实例（未使用）
            field: 要验证的字段

        Raises:
            ValidationError: 当headers格式不符合要求时抛出

        """
        for header in field.data:
            if not isinstance(header, dict):
                error_msg = "headers字段必须是一个字典列表"
                raise ValidationError(error_msg)
            if set(header.keys()) != {"key", "value"}:
                error_msg = "每个header字典必须包含key和value字段"
                raise ValidationError(error_msg)


class GetApiToolProviderResp(Schema):
    """API工具提供者响应模式类

    用于序列化API工具提供者的响应数据，定义了返回给客户端的数据结构
    """

    id = fields.UUID()  # 工具提供者的唯一标识符
    name = fields.String()  # 工具提供者的名称
    icon = fields.String()  # 工具提供者的图标URL
    openapi_schema = fields.String()  # OpenAPI规范的模式定义
    headers = fields.List(fields.Dict(), default=[])  # API请求头配置列表
    created_at = fields.Integer(default=0)  # 创建时间戳

    @pre_dump
    def process_data(self, data: ApiToolProvider, **kwargs: dict) -> dict:
        """处理ApiToolProvider对象数据

        在序列化前将ApiToolProvider对象转换为字典格式

        Args:
            data: ApiToolProvider对象实例
            **kwargs: 额外的关键字参数

        Returns:
            dict: 包含序列化数据的字典

        """
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "openapi_schema": data.openapi_schema,
            "headers": data.headers,
            "created_at": int(data.created_at.timestamp()),
        }


class GetApiToolResp(Schema):
    """API工具响应模式类，用于序列化API工具数据"""

    id = fields.UUID()  # 工具的唯一标识符
    name = fields.String()  # 工具名称
    description = fields.String()  # 工具描述
    inputs = fields.List(fields.Dict, default=[])  # 工具输入参数列表
    provider = fields.Dict()  # 工具提供者信息

    @pre_dump
    def process_data(self, data: ApiTool, **kwargs: dict) -> dict:
        """在序列化前处理API工具数据

        Args:
            data: ApiTool对象，包含工具的基本信息和参数
            **kwargs: 额外的关键字参数

        Returns:
            dict: 处理后的工具数据字典，包含以下字段：
                - id: 工具ID
                - name: 工具名称
                - description: 工具描述
                - inputs: 处理后的输入参数列表（移除了"in"字段）
                - provider: 提供者详细信息，包括ID、名称、图标、描述和请求头配置

        """
        provider = data.provider
        return {
            "id": data.id,
            "name": data.name,
            "description": data.description,
            "inputs": [
                {k: v for k, v in parameter.items() if k != "in"}
                for parameter in data.parameters
            ],
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "icon": provider.icon,
                "description": provider.description,
                "headers": provider.headers,
            },
        }


class GetApiToolProvidersWithPageReq(PaginatorReq):
    """分页获取API工具提供者的请求参数类"""

    # 搜索关键词，用于筛选工具提供者
    search_word = StringField(
        "search_word",
        validators=[Optional()],
    )


class GetApiToolProvidersWithPageResp(Schema):
    """API工具提供者分页查询响应模式类

    用于定义分页查询API工具提供者时的响应数据结构，包含：
    - 工具提供者基本信息（id、名称、图标等）
    - 工具提供者的API请求头配置
    - 工具提供者下的工具列表
    - 创建时间戳
    """

    id = fields.UUID()  # 工具提供者的唯一标识符
    name = fields.String()  # 工具提供者的名称
    icon = fields.String()  # 工具提供者的图标URL
    description = fields.String()  # 工具提供者的描述信息
    headers = fields.List(fields.Dict, default=[])  # API请求头配置列表
    tools = fields.List(fields.Dict, default=[])  # 工具提供者下的工具列表
    created_at = fields.Integer(default=0)  # 创建时间戳

    @pre_dump
    def process_data(self, data: ApiToolProvider, **kwargs: dict) -> dict:
        """处理API工具提供者数据，转换为响应格式

        Args:
            data: ApiToolProvider对象，包含工具提供者的原始数据
            **kwargs: 额外的关键字参数

        Returns:
            dict: 格式化后的响应数据字典

        """
        tools = data.tools  # 获取工具提供者下的所有工具
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "headers": data.headers,
            "tools": [
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                    # 处理工具参数，过滤掉"in"字段
                    "inputs": [
                        {k: v for k, v in parameter.items() if k != "in"}
                        for parameter in tool.parameters
                    ],
                }
                for tool in tools  # 遍历所有工具，构建工具列表
            ],
            "created_at": int(data.created_at.timestamp()),  # 转换时间戳为整数
        }
