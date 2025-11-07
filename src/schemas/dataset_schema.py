from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import URL, DataRequired, Length, Optional

from src.schemas.swag_schema import form_schema


@form_schema
class CreateDatasetReq(FlaskForm):
    """创建数据集请求表单类

    用于验证创建数据集时的请求参数，包含数据集名称、图标和描述信息
    """

    name = StringField(
        "name",
        validators=[
            DataRequired("知识库名字不能为空"),
            Length(max=100, message="知识库名字不能超过100个字符"),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("知识库图标不能为空"),
            URL("知识库图标必须是一个有效的URL"),
        ],
    )
    description = StringField(
        "description",
        default="",
        validators=[
            Optional(),
            Length(max=2000, message="知识库描述不能超过2000个字符"),
        ],
    )
