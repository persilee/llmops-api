from datetime import datetime

from sqlalchemy import (
    UUID,
    BigInteger,
    Column,
    DateTime,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.extension.database_extension import db
from src.model.app import App
from src.model.conversation import Message


class AccountPoints(db.Model):
    """用户积分账户表"""

    __tablename__ = "account_points"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_points_id"),
        Index("idx_account_points_account_id", "account_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表主键ID"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联账户ID（外键关联account表）"},
    )
    total_points = Column(
        Numeric(10, 2),
        nullable=False,
        server_default=text("0"),
        info={"description": "总积分（累计获取的积分，含已扣除）"},
    )
    available_points = Column(
        Numeric(10, 2),
        nullable=False,
        server_default=text("0"),
        info={"description": "可用积分（可抵扣token的积分）"},
    )
    frozen_points = Column(
        Numeric(10, 2),
        nullable=False,
        server_default=text("0"),
        info={"description": "冻结积分（未生效/锁定的积分）"},
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
    def points_to_tokens(self) -> int:
        """积分转token（1积分=1000token）"""
        return self.available_points * 1000

    @staticmethod
    def tokens_to_points(token_count: int) -> int:
        """token转积分（1000token=1积分）"""
        return round((token_count / 1000), 2)


class PointsTransaction(db.Model):
    """积分变动记录表"""

    __tablename__ = "points_transaction"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_points_transaction_id"),
        Index("idx_points_transaction_account_id", "account_id"),
        Index("idx_points_transaction_order_id", "order_id"),
        Index("idx_points_transaction_message_id", "message_id"),
        Index("idx_points_transaction_transaction_type", "transaction_type"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表主键ID"},
    )
    account_id = Column(UUID, nullable=False, info={"description": "关联账户ID"})
    transaction_type = Column(
        String(50),
        nullable=False,
        info={
            "description": (
                "变动类型：RECHARGE(充值)、DEDUCT(扣除)、REFUND(退款)、"
                "FREEZE(冻结)、UNFREEZE(解冻)"
            ),
        },
    )
    deduct_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "扣除来源，如订单号、活动ID等"},
    )
    points_amount = Column(
        Numeric(10, 2),  # 总共10位数字，其中2位小数
        nullable=False,
        info={"description": "变动积分（正数=增加，负数=减少）"},
    )
    token_amount = Column(
        BigInteger,
        nullable=True,
        info={"description": "关联token数（仅扣除场景，记录抵扣的token数）"},
    )
    order_id = Column(
        UUID,
        nullable=True,
        info={"description": "关联充值订单ID（充值场景）"},
    )
    message_id = Column(
        UUID,
        nullable=True,
        info={"description": "关联消息ID（扣除场景，外键关联message表）"},
    )
    app_id = Column(
        UUID,
        nullable=True,
        info={"description": "关联Agent App ID（扣除场景，外键关联 app 表）"},
    )
    transaction_desc = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={
            "description": (
                "变动描述（如：'充值1000积分'、'抵扣消息token消耗2000token'）"
            ),
        },
    )
    transaction_meta = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "元数据（扩展字段，如充值渠道、支付方式等）"},
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
    def app(self) -> "App | None":
        """获取应用名称

        优先从 app_id 获取应用名称，如果 app_id 为空则从 message_id 关联的记录中获取

        Returns:
            App | None: 应用名称

        """
        if self.app_id:
            return db.session.query(App).get(self.app_id)

        if self.message_id:
            message = db.session.query(Message).get(self.message_id)
            if message and message.app_id:
                return db.session.query(App).get(message.app_id)

        return None
