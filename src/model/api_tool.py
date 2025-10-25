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
from src.model.api_tool_provider import ApiToolProvider
from src.schemas.swag_schema import swagger_schema


@swagger_schema
class ApiTool(db.Model):
    """API工具模型"""

    __tablename__ = "api_tool"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_tool_id"),
        Index("idx_api_tool_account_id", "account_id"),
        Index("idx_api_tool_provider_id_name", "provider_id", "name"),
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
        info={"description": "关联用户 Id"},
    )
    provider_id = Column(
        UUID,
        nullable=False,
        info={"description": "提供者 Id"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "工具名字"},
    )
    description = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "工具描述"},
    )
    url = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "API 工具 url 地址"},
    )
    method = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "请求方法"},
    )
    parameters = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "API 接口的参数列表信息，类型为 json"},
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

    @property
    def provider(self) -> "ApiToolProvider":
        return db.session.query(ApiToolProvider).get(self.provider_id)
