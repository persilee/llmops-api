from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import UUID, DataRequired

from src.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from src.core.builtin_apps.entities.category_entity import CategoryEntity
from src.schemas.swag_schema import req_schema


class GetBuiltinAppCategoriesResp(Schema):
    """获取内置应用分类列表响应"""

    category = fields.String(dump_default="")
    name = fields.String(dump_default="")

    @pre_dump
    def process_data(self, data: CategoryEntity, **kwargs: dict) -> dict:
        return data.model_dump()


class GetBuiltinAppsResp(Schema):
    """获取内置应用实体列表响应"""

    id = fields.String(dump_default="")
    category = fields.String(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    model_config = fields.Dict(dump_default={})
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: BuiltinAppEntity, **kwargs: dict) -> dict:
        return {
            **data.model_dump(
                include={"id", "category", "name", "icon", "description", "created_at"},
            ),
            "model_config": {
                "provider": data.language_model_config.get("provider", ""),
                "model": data.language_model_config.get("model", ""),
            },
        }


@req_schema
class AddBuiltinAppToSpaceReq(FlaskForm):
    """添加内置应用到个人空间请求"""

    builtin_app_id = StringField(
        "builtin_app_id",
        default="",
        validators=[
            DataRequired("内置应用id不能为空"),
            UUID("内置工具id格式必须为UUID"),
        ],
    )
