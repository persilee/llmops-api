from flask import current_app
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

from src.entity.conversation_entity import InvokeFrom
from src.extension.database_extension import db
from src.model.conversation import Conversation


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
    assistant_agent_conversation_id = Column(
        UUID,
        nullable=True,
        info={"description": "辅助智能体会话id"},
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

    @property
    def assistant_agent_conversation(self) -> "Conversation":
        """只读属性，返回当前账号的辅助Agent会话"""
        # 1.获取辅助Agent应用id
        assistant_agent_id = current_app.config.get("ASSISTANT_AGENT_ID")
        conversation = (
            db.session.query(Conversation).get(self.assistant_agent_conversation_id)
            if self.assistant_agent_conversation_id
            else None
        )

        # 2.判断会话信息是否存在，如果不存在则创建一个空会话
        if not self.assistant_agent_conversation_id or not conversation:
            # 3.开启自动提交上下文
            with db.auto_commit():
                # 4.创建辅助Agent会话
                conversation = Conversation(
                    app_id=assistant_agent_id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.ASSISTANT_AGENT,
                    created_by=self.id,
                )
                db.session.add(conversation)
                db.session.flush()

                # 5.更新当前账号的辅助Agent会话id
                self.assistant_agent_conversation_id = conversation.id

        return conversation


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
