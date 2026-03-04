from datetime import datetime

from sqlalchemy import (
    UUID,
    BigInteger,
    Column,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    text,
)

from src.extension.database_extension import db


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
        BigInteger,
        nullable=False,
        server_default=text("0"),
        info={"description": "总积分（累计获取的积分，含已扣除）"},
    )
    available_points = Column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
        info={"description": "可用积分（可抵扣token的积分）"},
    )
    frozen_points = Column(
        BigInteger,
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
        return token_count // 1000
