from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import URL, DataRequired, Length, Optional

from src.model.dataset import Dataset
from src.schemas.swag_schema import req_schema, resp_schema


@req_schema
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


@resp_schema()
class GetDatasetResp(Schema):
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    document_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    related_app_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "hit_count": data.hit_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "updated_at": int(data.updated_at.timestamp()),
            "created_at": int(data.created_at.timestamp()),
        }
