from flask_wtf import FlaskForm
from wtforms import StringField, ValidationError
from wtforms.validators import URL, DataRequired, Length

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
