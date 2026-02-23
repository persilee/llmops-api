from datetime import UTC, datetime

from flask import current_app
from flask_login import UserMixin
from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Index,
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
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_id"),
        Index("idx_account_email", "email"),
        Index("idx_account_phone", "phone_number"),
    )

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
        nullable=True,
        info={"description": "邮箱"},
    )
    phone_number = Column(
        String(20),
        nullable=True,
        info={"description": "手机号"},
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
    is_active = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        info={"description": "是否激活"},
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
                    name="新对话",
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
        Index("idx_account_oauth_account_id", "account_id"),
        Index("idx_account_oauth_openid_provider", "openid", "provider"),
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
        onupdate=datetime.now,
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )


class VerificationCode(db.Model):
    """验证码记录表模型"""

    __tablename__ = "verification_code"
    __table_args__ = (PrimaryKeyConstraint("id", name="pk_verification_code_id"),)

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "手机号或邮箱地址"},
    )
    code = Column(
        String(10),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "验证码"},
    )
    used = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        info={"description": "是否使用"},
    )
    expires_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "过期时间"},
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
    def is_valid(self) -> bool:
        """检查验证码是否有效

        Returns:
            bool: 如果验证码未被使用且未过期则返回True，否则返回False

        """
        # 获取当前UTC时间
        now = datetime.now(UTC)
        # 确保 self.expires_at 也是aware datetime
        if self.expires_at.tzinfo is None:
            # 如果expires_at是naive，将其转换为aware
            self.expires_at = self.expires_at.replace(tzinfo=UTC)
        # 验证码有效的条件：未被使用且未超过过期时间
        return not self.used and now < self.expires_at


    def mark_as_used(self) -> bool:
        """将验证码标记为已使用

        设置used标志为True，并将更改提交到数据库。
        这个方法用于在验证码被成功使用后更新其状态。
        """
        self.used = True
        db.session.commit()
        return True
