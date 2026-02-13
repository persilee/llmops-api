from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired, FileSize
from wtforms.fields import StringField
from wtforms.validators import DataRequired

from src.schemas.swag_schema import req_schema


@req_schema
class AudioToTextReq(FlaskForm):
    """语音转文本请求结构"""

    file = FileField(
        "file",
        validators=[
            FileRequired(message="转换音频文件不能为空"),
            FileSize(max_size=25 * 1024 * 1024, message="音频文件不能超过25MB"),
            FileAllowed(["webm", "wav", "mp4"], message="请上传正确的音频文件"),
        ],
    )


@req_schema
class MessageToAudioReq(FlaskForm):
    """消息转流式事件语音请求结构"""

    message_id = StringField(
        "message_id",
        validators=[
            DataRequired(message="消息id不能为空"),
        ],
    )
