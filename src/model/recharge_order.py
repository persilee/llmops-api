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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.extension.database_extension import db


class RechargeOrder(db.Model):
    """积分充值订单表"""

    __tablename__ = "recharge_order"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_recharge_order_id"),
        Index("idx_recharge_order_account_id", "account_id"),
        Index("idx_recharge_order_order_no", "order_no"),
        Index("idx_recharge_order_pay_status", "pay_status"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表主键ID"},
    )
    order_no = Column(
        String(64),
        nullable=False,
        unique=True,
        info={"description": "订单编号（唯一，如：RE202405200001）"},
    )
    account_id = Column(UUID, nullable=False, info={"description": "充值账户ID"})
    points_amount = Column(
        BigInteger,
        nullable=False,
        info={"description": "充值积分数量"},
    )
    amount = Column(
        Numeric(10, 2),
        nullable=False,
        info={"description": "充值金额（元），按1000积分=4.8元计算"},
    )
    pay_status = Column(
        String(20),
        nullable=False,
        server_default=text("UNPAID"),
        info={
            "description": (
                "支付状态：UNPAID(未支付)、PAID(已支付)、"
                "REFUNDED(已退款)、CANCELED(已取消)"
            ),
        },
    )
    pay_channel = Column(
        String(50),
        nullable=True,
        info={"description": "支付渠道：ALIPAY(支付宝)、WECHAT(微信)、BANK(银行卡)"},
    )
    pay_time = Column(DateTime, nullable=True, info={"description": "支付完成时间"})
    refund_time = Column(DateTime, nullable=True, info={"description": "退款时间"})
    order_meta = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "订单元数据（如支付流水号、回调参数等）"},
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

    @staticmethod
    def calculate_amount(points: int) -> float:
        """根据积分计算充值金额（1000积分=4.8元）"""
        return round((points / 1000) * 4.8, 2)

    @staticmethod
    def calculate_points(amount: float) -> int:
        """根据金额计算充值积分（4.8元=1000积分）"""
        return int((amount / 4.8) * 1000)
