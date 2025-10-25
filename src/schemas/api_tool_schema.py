from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired


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
