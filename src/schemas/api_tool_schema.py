from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, ValidationError
from wtforms.validators import URL, UUID, DataRequired, Length

from src.model.api_tool_provider import ApiToolProvider
from src.schemas.schema import ListField


class ValidateGetToolAPIProviderReq(FlaskForm):
    """获取工具API提供者请求的表单验证类

    用于验证获取特定工具API提供者时的请求参数
    """

    provider_id = StringField(
        "provider_id",
        validators=[
            DataRequired(message="provider_id不能为空"),  # 验证provider_id字段不能为空
            UUID(
                message="provider_id必须是有效的UUID格式",
            ),  # 验证provider_id必须是有效的UUID格式
        ],
    )


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
