from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import BooleanField, StringField
from wtforms.validators import DataRequired, Optional, ValidationError

from pkg.paginator import PaginatorReq
from src.entity.dataset_entity import KEYWORD_MAX_LENGTH
from src.lib.helper import datetime_to_timestamp
from src.model import Segment
from src.schemas.swag_schema import req_schema, resp_schema

from .schema import ListField


@req_schema
class GetSegmentsWithPageReq(PaginatorReq):
    """获取文档片段列表请求"""

    search_word = StringField("search_word", default="", validators=[Optional()])


@resp_schema()
class GetSegmentsWithPageResp(Schema):
    """获取文档片段列表响应结构"""

    id = fields.UUID(dump_default="")
    document_id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    position = fields.Integer(dump_default=0)
    content = fields.String(dump_default="")
    keywords = fields.List(fields.String, dump_default=[])
    character_count = fields.Integer(dump_default=0)
    token_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    enabled = fields.Boolean(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Segment, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "document_id": data.document_id,
            "dataset_id": data.dataset_id,
            "position": data.position,
            "content": data.content,
            "keywords": data.keywords,
            "character_count": data.character_count,
            "token_count": data.token_count,
            "hit_count": data.hit_count,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


@resp_schema()
class GetSegmentResp(Schema):
    """获取文档详情响应结构"""

    id = fields.UUID(dump_default="")
    document_id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    position = fields.Integer(dump_default=0)
    content = fields.String(dump_default="")
    keywords = fields.List(fields.String, dump_default=[])
    character_count = fields.Integer(dump_default=0)
    token_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    hash = fields.String(dump_default="")
    enabled = fields.Boolean(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Segment, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "document_id": data.document_id,
            "dataset_id": data.dataset_id,
            "position": data.position,
            "content": data.content,
            "keywords": data.keywords,
            "character_count": data.character_count,
            "token_count": data.token_count,
            "hit_count": data.hit_count,
            "hash": data.hash,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


@req_schema
class UpdateSegmentEnabledReq(FlaskForm):
    """更新文档片段启用状态请求"""

    enabled = BooleanField("enabled")

    def validate_enabled(self, field: BooleanField) -> None:
        """校验文档启用状态enabled"""
        if not isinstance(field.data, bool):
            error_msg = "enabled状态不能为空且必须为布尔值"
            raise ValidationError(error_msg)


@req_schema
class CreateSegmentReq(FlaskForm):
    """创建文档片段请求结构"""

    content = StringField("content", validators=[DataRequired("片段内容不能为空")])
    keywords = ListField("keywords")

    def validate_keywords(self, field: ListField) -> None:
        """校验关键词列表，涵盖长度不能为空，默认为值为空列表"""
        # 1.校验数据类型+非空
        if field.data is None:
            field.data = []
        if not isinstance(field.data, list):
            error_msg = "关键词列表格式必须是数组"
            raise ValidationError(error_msg)

        # 2.校验数据的长度，最长不能超过10个关键词
        if len(field.data) > KEYWORD_MAX_LENGTH:
            error_msg = "关键词长度范围数量在1-10"
            raise ValidationError(error_msg)

        # 3.循环校验关键词信息，关键词必须是字符串
        for keyword in field.data:
            if not isinstance(keyword, str):
                error_msg = "关键词必须是字符串"
                raise ValidationError(error_msg)

        # 4.删除重复数据并更新
        field.data = list(dict.fromkeys(field.data))


@req_schema
class UpdateSegmentReq(FlaskForm):
    """更新文档片段请求"""

    content = StringField("content", validators=[DataRequired("片段内容不能为空")])
    keywords = ListField("keywords")

    def validate_keywords(self, field: ListField) -> None:
        """校验关键词列表，涵盖长度不能为空，默认为值为空列表"""
        # 1.校验数据类型+非空
        if field.data is None:
            field.data = []
        if not isinstance(field.data, list):
            error_msg = "关键词列表格式必须是数组"
            raise ValidationError(error_msg)

        # 2.校验数据的长度，最长不能超过10个关键词
        if len(field.data) > KEYWORD_MAX_LENGTH:
            error_msg = "关键词长度范围数量在1-10"
            raise ValidationError(error_msg)

        # 3.循环校验关键词信息，关键词必须是字符串
        for keyword in field.data:
            if not isinstance(keyword, str):
                error_msg = "关键词必须是字符串"
                raise ValidationError(error_msg)

        # 4.删除重复数据并更新
        field.data = list(dict.fromkeys(field.data))
