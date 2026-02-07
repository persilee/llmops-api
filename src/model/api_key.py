from datetime import datetime

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)

from src.extension.database_extension import db
from src.model.account import Account


class ApiKey(db.Model):
    """API密钥模型"""

    __tablename__ = "api_key"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_key_id"),
        UniqueConstraint("api_key", name="uk_api_key_api_key"),
        UniqueConstraint("account_id", "api_key", name="uk_api_key_account_id_api_key"),
        Index("idx_api_key_account_id", "account_id"),
        Index("idx_api_key_api_key", "api_key"),
    )

    id = Column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        info={"description": "用户关联 Id"},
    )
    api_key = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "加密后的 api 密钥"},
    )
    is_active = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        info={"description": "是否激活，true 表示可以正常使用，false 表示禁止使用"},
    )
    remark = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "备注信息"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )

    @property
    def account(self) -> "Account":
        """只读属性，返回该秘钥归属的账号信息"""
        return db.session.query(Account).get(self.account_id)
