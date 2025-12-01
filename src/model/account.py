from flask_login import UserMixin
from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)

from src.extension.database_extension import db


class Account(UserMixin, db.Model):
    """用户账号模型"""

    __tablename__ = "account"
    __table_args__ = (PrimaryKeyConstraint("id", name="pk_account_id"),)

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "名字"},
    )
    email = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "邮箱"},
    )
    avatar = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "头像"},
    )
    password = Column(
        String(255),
        nullable=True,
        info={"description": "密码"},
    )
    password_salt = Column(
        String(255),
        nullable=True,
        info={"description": "密码盐值"},
    )
    last_login_at = Column(
        DateTime,
        nullable=True,
        info={"description": "最后登录时间"},
    )
    last_login_ip = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "最后登录 ip"},
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
    def is_password_set(self) -> bool:
        return self.password is not None and self.password != ""


class AccountOAuth(db.Model):
    """第三方授权认证账号模型"""

    __tablename__ = "account_oauth"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_oauth_id"),
        UniqueConstraint(
            "account_id",
            "provider",
            name="uk_account_oauth_account_id_provider",
        ),
        UniqueConstraint("provider", "openid", name="uk_account_oauth_provider_openid"),
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
        info={"description": "账号 id"},
    )
    provider = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "提供商名字"},
    )
    openid = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "第三方平台唯一标识"},
    )
    encrypted_token = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "密钥信息"},
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
