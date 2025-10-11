"""应用模型模块.

该模块定义了应用程序的数据库模型，包含应用的基本信息，
如ID、所属账户ID、名称、图标、描述以及时间戳等字段。
"""

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

from src.extension import db
from src.schemas import swagger_schema


@swagger_schema
class App(db.Model):
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),
        Index("idx_app_account_id", "account_id"),
    )

    id = Column(
        UUID,
        server_default=text("uuid_generate_v4()"),
        nullable=False,
        info={"description": "应用ID"},
    )
    account_id = Column(UUID, info={"description": "所属账户ID"})
    name = Column(
        String(255),
        server_default=text("''::character varying"),
        nullable=False,
        info={"description": "应用名称"},
    )
    icon = Column(
        String(255),
        server_default=text("''::character varying"),
        nullable=False,
        info={"description": "应用图标"},
    )
    description = Column(
        Text,
        server_default=text("''::text"),
        nullable=False,
        info={"description": "应用描述"},
    )
    status = Column(
        String(255),
        server_default=text("''::character varying"),
        nullable=False,
        info={"description": "应用状态"},
    )
    updated_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        nullable=False,
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        nullable=False,
        info={"description": "创建时间"},
    )
