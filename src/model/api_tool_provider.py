from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.extension.database_extension import db
from src.schemas.swag_schema import swagger_schema


@swagger_schema
class ApiToolProvider(db.Model):
    """API工具提供者模型"""

    __tablename__ = "api_tool_provider"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_tool_provider_id"),
        Index("idx_api_tool_provider_account_id_name", "account_id", "name"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联用户 id"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "提供者名字"},
    )
    icon = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "提供者图标 url 地址"},
    )
    description = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "提供者描述"},
    )
    openapi_schema = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "接口的 openapi 规范描述"},
    )
    headers = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "api 接口需要 headers 请求头数据，类型为列表"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )
