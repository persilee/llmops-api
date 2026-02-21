from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import URL, DataRequired, Length, regexp

from pkg.password import AUTH_CREDENTIAL_FORMAT
from src.lib.helper import datetime_to_timestamp
from src.model import Account
from src.schemas.auth_schema import EMAIL_FORMAT, PHONE_NUMBER_FORMAT
from src.schemas.swag_schema import req_schema, resp_schema


@resp_schema()
class GetCurrentUserResp(Schema):
    """获取当前登录账号信息响应"""

    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    email = fields.String(dump_default="")
    avatar = fields.String(dump_default="")
    last_login_at = fields.Integer(dump_default=0)
    last_login_ip = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Account, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "name": data.name,
            "email": data.email,
            "avatar": data.avatar,
            "last_login_at": datetime_to_timestamp(data.last_login_at),
            "last_login_ip": data.last_login_ip,
            "created_at": datetime_to_timestamp(data.created_at),
        }


@req_schema
class UpdatePasswordReq(FlaskForm):
    """更新账号密码请求"""

    password = StringField(
        "password",
        validators=[
            DataRequired("登录密码不能为空"),
            regexp(
                regex=AUTH_CREDENTIAL_FORMAT,
                message="密码最少包含一个字母、一个数字，并且长度是8-16",
            ),
        ],
    )


@req_schema
class UpdateNameReq(FlaskForm):
    """更新账号名称请求"""

    name = StringField(
        "name",
        validators=[
            DataRequired("账号名字不能为空"),
            Length(min=3, max=30, message="账号名称长度在3-30位"),
        ],
    )


@req_schema
class UpdateAvatarReq(FlaskForm):
    """更新账号头像请求"""

    avatar = StringField(
        "avatar",
        validators=[
            DataRequired("账号头像不能为空"),
            URL("账号头像必须是URL图片地址"),
        ],
    )


@req_schema
class BindPhoneNumberReq(FlaskForm):
    """绑定手机号请求"""

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
            Length(min=6, max=6, message="验证码长度为6位"),
        ],
    )


@req_schema
class BindEmailReq(FlaskForm):
    """绑定邮箱请求"""

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

    code = StringField(
        "code",
        validators=[
            DataRequired("验证码不能为空"),
            Length(min=6, max=6, message="验证码长度为6位"),
        ],
    )
