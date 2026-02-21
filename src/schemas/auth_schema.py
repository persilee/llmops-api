from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import DataRequired, Email, Length, regexp

from pkg.password import AUTH_CREDENTIAL_FORMAT
from src.schemas.swag_schema import req_schema, resp_schema

# 手机号码格式验证的正则表达式
PHONE_NUMBER_FORMAT = r"^1[3-9]\d{9}$"
# 邮箱格式验证的正则表达式
EMAIL_FORMAT = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


@req_schema
class PasswordLoginReq(FlaskForm):
    """账号密码登录请求结构"""

    email = StringField(
        "email",
        validators=[
            DataRequired("登录邮箱不能为空"),
            Email("登录邮箱格式错误"),
            Length(min=5, max=254, message="登录邮箱长度在5-254个字符"),
        ],
    )
    password = StringField(
        "password",
        validators=[
            DataRequired("账号密码不能为空"),
            regexp(
                regex=AUTH_CREDENTIAL_FORMAT,
                message="密码最少包含一个字母，一个数字，并且长度为8-16",
            ),
        ],
    )


@req_schema
class PhoneNumberLoginReq(FlaskForm):
    """手机号登录请求结构"""

    phone_number = StringField(
        "phone_number",
        validators=[
            DataRequired("手机号不能为空"),
            regexp(
                regex=PHONE_NUMBER_FORMAT,
                message="手机号格式错误",
            ),
        ],
    )
    code = StringField(
        "code",
        validators=[
            DataRequired("验证码不能为空"),
            Length(min=6, max=6, message="验证码长度为6个字符"),
        ],
    )


@req_schema
class SendSMSCodeReq(FlaskForm):
    """发送短信验证码请求结构"""

    phone_number = StringField(
        "phone_number",
        validators=[
            DataRequired("手机号不能为空"),
            regexp(
                regex=PHONE_NUMBER_FORMAT,
                message="手机号格式错误",
            ),
        ],
    )


@req_schema
class SendMailCodeReq(FlaskForm):
    """发送邮件验证码请求结构"""

    email = StringField(
        "email",
        validators=[
            DataRequired("邮箱不能为空"),
            regexp(
                regex=EMAIL_FORMAT,
                message="邮箱格式错误",
            ),
        ],
    )


@resp_schema()
class LoginResp(Schema):
    """授权认证响应结构"""

    access_token = fields.String()
    expire_at = fields.Integer()
    user_id = fields.String()
    session_id = fields.String()
    is_new_user = fields.Boolean()
