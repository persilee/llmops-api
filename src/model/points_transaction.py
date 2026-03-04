from datetime import datetime

from sqlalchemy import (
    UUID,
    BigInteger,
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
    points_amount = Column(
        BigInteger,
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
