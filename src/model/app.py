"""应用模型模块.

该模块定义了应用程序的数据库模型，包含应用的基本信息，
如ID、所属账户ID、名称、图标、描述以及时间戳等字段。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)

from src.extension import db


class App(db.Model):
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),
        Index("idx_app_account_id", "account_id"),
    )

    id = Column(
        UUID,
        default=uuid.uuid4,
        nullable=False,
        info={"description": "应用ID"},
    )
    account_id = Column(UUID, nullable=False, info={"description": "所属账户ID"})
    name = Column(
        String(255),
        default="",
        nullable=False,
        info={"description": "应用名称"},
    )
    icon = Column(
        String(255),
        default="",
        nullable=False,
        info={"description": "应用图标"},
    )
    description = Column(
        Text,
        default="",
        nullable=False,
        info={"description": "应用描述"},
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now(UTC),
        nullable=False,
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
        info={"description": "创建时间"},
    )
