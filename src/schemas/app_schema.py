from urllib.parse import urlparse
from uuid import UUID

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import IntegerField, StringField
from wtforms.validators import (
    URL,
    DataRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from pkg.paginator import PaginatorReq
from src.entity.app_entity import MAX_IMAGE_COUNT, AppStatus
from src.lib.helper import datetime_to_timestamp
from src.model import App, AppConfigVersion, Message
from src.schemas.schema import ListField
from src.schemas.swag_schema import req_schema, resp_schema


@req_schema
class CreateAppReq(FlaskForm):
    """创建Agent应用请求结构体"""

    name = StringField(
        "name",
        validators=[
            DataRequired("应用名称不能为空"),
            Length(max=40, message="应用名称长度最大不能超过40个字符"),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("应用图标不能为空"),
            URL(message="应用图标必须是图片URL链接"),
        ],
    )
    description = StringField(
        "description",
        validators=[Length(max=800, message="应用描述的长度不能超过800个字符")],
    )


@req_schema
class UpdateAppReq(FlaskForm):
    """更新Agent应用请求结构体"""

    name = StringField(
        "name",
        validators=[
            DataRequired("应用名称不能为空"),
            Length(max=40, message="应用名称长度最大不能超过40个字符"),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("应用图标不能为空"),
            URL(message="应用图标必须是图片URL链接"),
        ],
    )
    description = StringField(
        "description",
        validators=[Length(max=800, message="应用描述的长度不能超过800个字符")],
    )


class GetAppsWithPageReq(PaginatorReq):
    """获取应用分页列表数据请求"""

    search_word = StringField("search_word", default="", validators=[Optional()])


class GetAppsWithPageResp(Schema):
    """获取应用分页列表数据响应结构"""

    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    preset_prompt = fields.String(dump_default="")
    model_config = fields.Dict(dump_default={})
    status = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs: dict) -> dict:
        app_config = (
            data.app_config
            if data.status == AppStatus.PUBLISHED
            else data.draft_app_config
        )
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "preset_prompt": app_config.preset_prompt,
            "model_config": {
                "provider": app_config.model_config.get("provider", ""),
                "model": app_config.model_config.get("model", ""),
            },
            "status": data.status,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


@resp_schema()
class GetAppResp(Schema):
    """获取应用基础信息响应结构"""

    id = fields.UUID(dump_default="")
    debug_conversation_id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    draft_updated_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "debug_conversation_id": data.debug_conversation_id
            if data.debug_conversation_id
            else "",
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "status": data.status,
            "draft_updated_at": datetime_to_timestamp(data.draft_app_config.updated_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


@req_schema
class GetPublishHistoriesWithPageReq(PaginatorReq):
    """获取应用发布历史配置分页列表请求"""


@resp_schema()
class GetPublishHistoriesWithPageResp(Schema):
    """获取应用发布历史配置列表分页数据"""

    id = fields.UUID(dump_default="")
    version = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: AppConfigVersion, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "version": data.version,
            "created_at": datetime_to_timestamp(data.created_at),
        }


@req_schema
class FallbackHistoryToDraftReq(FlaskForm):
    """回退历史版本到草稿请求结构体"""

    app_config_version_id = StringField(
        "app_config_version_id",
        validators=[DataRequired("回退配置版本id不能为空")],
    )

    def validate_app_config_version_id(self, field: StringField) -> None:
        """校验回退配置版本id"""
        try:
            UUID(field.data)
        except Exception as e:
            error_msg = "回退配置版本id必须为UUID"
            raise ValidationError(error_msg) from e


@req_schema
class GenerateShareConversationReq(FlaskForm):
    """生成分享回话请求结构体"""

    conversation_id = StringField(
        "conversation_id",
        validators=[DataRequired("回话id不能为空")],
    )
    message_ids = ListField("message_ids", default=[])

    def validate_conversation_id(self, field: StringField) -> None:
        """校验回话id"""
        try:
            UUID(field.data)
        except Exception as e:
            error_msg = "回话id必须为UUID"
            raise ValidationError(error_msg) from e

    def validate_message_ids(self, field: ListField) -> None:
        if not isinstance(field.data, list):
            return

        for message_id in field.data:
            try:
                UUID(message_id)
            except Exception as e:
                error_msg = "消息id必须为UUID"
                raise ValidationError(error_msg) from e


@req_schema
class UpdateDebugConversationSummaryReq(FlaskForm):
    """更新应用调试会话长期记忆请求体"""

    summary = StringField("summary", default="")


@req_schema
class DebugChatReq(FlaskForm):
    """应用调试会话请求结构体"""

    image_urls = ListField("image_urls", default=[])
    query = StringField(
        "query",
        validators=[
            DataRequired("用户提问query不能为空"),
        ],
    )

    def validate_image_urls(self, field: ListField) -> None:
        """校验传递的图片URL链接列表"""
        # 1.校验数据类型如果为None则设置默认值空列表
        if not isinstance(field.data, list):
            return

        # 2.校验数据的长度，最多不能超过5条URL记录
        if len(field.data) > MAX_IMAGE_COUNT:
            error_msg = f"上传的图片数量不能超过{MAX_IMAGE_COUNT}，请核实后重试"
            raise ValidationError(error_msg)

        # 3.循环校验image_url是否为URL
        for image_url in field.data:
            result = urlparse(image_url)
            if not all([result.scheme, result.netloc]):
                error_msg = "上传的图片URL地址格式错误，请核实后重试"
                raise ValidationError(error_msg)


@req_schema
class GetDebugConversationMessagesWithPageReq(PaginatorReq):
    """获取调试会话消息列表分页请求结构体"""

    created_at = IntegerField(
        "created_at",
        default=0,
        validators=[Optional(), NumberRange(min=0, message="created_at游标最小值为0")],
    )


class GetDebugConversationMessagesWithPageResp(Schema):
    """获取调试会话消息列表分页响应结构体"""

    id = fields.UUID(dump_default="")
    conversation_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    image_urls = fields.List(fields.String, dump_default=[])
    answer = fields.String(dump_default="")
    total_token_count = fields.Integer(dump_default=0)
    latency = fields.Float(dump_default=0)
    agent_thoughts = fields.List(fields.Dict, dump_default=[])
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Message, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "conversation_id": data.conversation_id,
            "query": data.query,
            "image_urls": data.image_urls,
            "answer": data.answer,
            "total_token_count": data.total_token_count,
            "latency": data.latency,
            "agent_thoughts": [
                {
                    "id": agent_thought.id,
                    "position": agent_thought.position,
                    "event": agent_thought.event,
                    "thought": agent_thought.thought,
                    "observation": agent_thought.observation,
                    "tool": agent_thought.tool,
                    "tool_input": agent_thought.tool_input,
                    "latency": agent_thought.latency,
                    "created_at": datetime_to_timestamp(agent_thought.created_at),
                }
                for agent_thought in data.agent_thoughts
            ],
            "created_at": datetime_to_timestamp(data.created_at),
        }
