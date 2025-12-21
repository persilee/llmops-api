from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    UniqueConstraint,
    text,
)

from src.extension.database_extension import db


class EndUser(db.Model):
    """终端用户模型"""

    __tablename__ = "end_user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_end_user_id"),
        UniqueConstraint("tenant_id", "app_id", "id", name="uk_end_user_tenant_app_id"),
        Index("idx_end_user_tenant_id", "tenant_id"),
        Index("idx_end_user_app_id", "app_id"),
        Index("idx_end_user_tenant_app", "tenant_id", "app_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    tenant_id = Column(
        UUID,
        nullable=False,
        info={"description": "归属账号 id"},
    )
    app_id = Column(
        UUID,
        nullable=False,
        info={"description": "归属应用 Id"},
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
