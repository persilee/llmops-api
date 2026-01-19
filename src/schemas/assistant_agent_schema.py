from urllib.parse import urlparse

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import IntegerField, StringField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError

from pkg.paginator import PaginatorReq
from src.entity.app_entity import MAX_IMAGE_COUNT
from src.lib.helper import datetime_to_timestamp
from src.model import Message
from src.schemas.swag_schema import req_schema, resp_schema

from .schema import ListField


@req_schema
class AssistantAgentChat(FlaskForm):
    """辅助Agent会话请求结构体"""

    image_urls = ListField("image_urls", default=[])
    query = StringField(
        "query",
        validators=[
            DataRequired("用户提问query不能为空"),
        ],
    )

    def validate_image_urls(self, field: ListField) -> list | None:
        """校验传递的图片URL链接列表"""
        # 1.校验数据类型如果为None则设置默认值空列表
        if not isinstance(field.data, list):
            return []

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

        return None


@req_schema
class GetAssistantAgentMessagesWithPageReq(PaginatorReq):
    """获取辅助智能体消息列表分页请求"""

    created_at = IntegerField(
        "created_at",
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0, message="created_at游标最小值为0"),
        ],
    )


@resp_schema()
class GetAssistantAgentMessagesWithPageResp(Schema):
    """获取辅助智能体消息列表分页响应结构"""

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
