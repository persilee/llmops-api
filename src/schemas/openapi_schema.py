import uuid
from urllib.parse import urlparse

from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField
from wtforms.validators import UUID, DataRequired, Optional, ValidationError

from src.entity.app_entity import MAX_IMAGE_COUNT
from src.schemas.swag_schema import req_schema

from .schema import ListField


@req_schema
class OpenAPIChatReq(FlaskForm):
    """开放API聊天接口请求结构体"""

    app_id = StringField(
        "app_id",
        validators=[
            DataRequired("应用id不能为空"),
            UUID("应用id格式必须为UUID"),
        ],
    )
    end_user_id = StringField(
        "end_user_id",
        default="",
        validators=[
            Optional(),
            UUID("终端用户id必须为UUID"),
        ],
    )
    conversation_id = StringField("conversation_id", default="")
    query = StringField(
        "query",
        default="",
        validators=[
            DataRequired("用户提问query不能为空"),
        ],
    )
    image_urls = ListField("image_urls", default=[])
    stream = BooleanField("stream", default=True)

    def validate_conversation_id(self, field: StringField) -> None:
        """自定义校验conversation_id函数"""
        # 1.检测是否传递数据，如果传递了，则类型必须为UUID
        if field.data:
            try:
                uuid.UUID(field.data)
            except Exception as e:
                error_msg = "会话id格式必须为UUID"
                raise ValidationError(error_msg) from e

            # 2.终端用户id是不是为空
            if not self.end_user_id.data:
                error_msg = "传递会话id则终端用户id不能为空"
                raise ValidationError(error_msg)

    def validate_image_urls(self, field: ListField) -> None:
        """校验传递的图片URL链接列表"""
        # 1.校验数据类型如果为None则设置默认值空列表
        if not isinstance(field.data, list):
            error_msg = "图片URL必须是列表格式"
            raise ValidationError(error_msg)

        # 2.校验数据的长度，最多不能超过5条URL记录
        if len(field.data) > MAX_IMAGE_COUNT:
            error_msg = "上传的图片数量不能超过5，请核实后重试"
            raise ValidationError(error_msg)

        # 3.循环校验image_url是否为URL
        for image_url in field.data:
            result = urlparse(image_url)
            if not all([result.scheme, result.netloc]):
                error_msg = "上传的图片URL地址格式错误，请核实后重试"
                raise ValidationError(error_msg)
