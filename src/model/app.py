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
    UniqueConstraint,
    text,
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


class AppDatasetJoin(db.Model):
    """知识库关联表模型（应用与知识库的关联关系）"""

    __tablename__ = "app_dataset_join"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_dataset_join_id"),
        # 联合唯一约束：确保同一应用与同一知识库仅存在一条关联记录
        UniqueConstraint(
            "app_id",
            "dataset_id",
            name="uk_app_dataset_join_app_dataset",
        ),
        Index("idx_app_dataset_join_app_id", "app_id"),
        Index("idx_app_dataset_join_dataset_id", "dataset_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    app_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联应用 id"},
    )
    dataset_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联知识库 id"},
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
