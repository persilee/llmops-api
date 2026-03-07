import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from injector import inject

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.exception.exception import FailException
from src.model.account_points import AccountPoints, PointsTransaction
from src.model.recharge_order import RechargeOrder
from src.service.base_service import BaseService

logger = logging.getLogger(__name__)


@inject
@dataclass
class PointsService(BaseService):
    db: SQLAlchemy

    def deduct_points_by_token(
        self,
        account_id: UUID,
        token_count: int,
        message_id: UUID | None = None,
        app_id: UUID | None = None,
    ) -> None:
        """根据token消耗扣除用户积分

        Args:
            account_id (UUID): 用户账户ID
            message_id (UUID): 消息ID，用于关联积分交易记录
            app_id (UUID): 应用ID
            token_count (int): 消耗的token数量

        Returns:
            None

        Raises:
            FailException: 当用户积分不足时抛出异常

        Note:
            - 积分计算规则：每1000个token扣除1积分
            - 如果token数量不足1000，不扣除积分
            - 操作会在数据库事务中执行，确保数据一致性

        """
        try:
            # 计算需要扣除的积分
            deduct_points = round(token_count / 1000, 2)
            if deduct_points <= 0:
                return
            # 开启数据库事务
            with self.db.auto_commit():
                # 获取用户积分账户（不存在则创建）
                points_account = (
                    self.db.session.query(AccountPoints)
                    .filter(AccountPoints.account_id == account_id)
                    .first()
                )
                if not points_account:
                    points_account = AccountPoints(account_id=account_id)
                    self.db.session.add(points_account)
                    self.db.session.flush()

                # 校验可用积分是否足够
                if points_account.available_points < deduct_points:
                    error_msg = "可用积分不足，无法抵扣token消耗"
                    raise FailException(error_msg) from None  # noqa: TRY301

                # 更新积分账户
                try:
                    deduct_points = Decimal(str(deduct_points))  # 转换为Decimal
                    points_account.available_points -= deduct_points
                    points_account.total_points -= deduct_points
                except Exception:
                    logger.exception(
                        "更新积分账户失败",
                        extra={
                            "account_id": account_id,
                            "deduct_points": deduct_points,
                        },
                    )
                    raise

                # 记录积分变动
                try:
                    transaction = PointsTransaction(
                        account_id=account_id,
                        transaction_type="DEDUCT",
                        points_amount=-deduct_points,  # 负数表示扣除
                        token_amount=token_count,
                        message_id=message_id,
                        app_id=app_id,
                        transaction_desc=f"抵扣消息token消耗{token_count}token，扣除{deduct_points}积分",
                    )
                    self.db.session.add(transaction)
                except Exception:
                    logger.exception("创建积分交易记录失败")
                    raise
        except FailException:
            # 业务异常，直接重新抛出
            raise
        except Exception:
            # 其他异常，记录日志并抛出
            logger.exception("扣除积分时发生未知错误")
            error_msg = "扣除积分时发生未知错误"
            raise FailException(error_msg) from None

    def create_recharge_order(
        self,
        account_id: UUID,
        amount: int,
    ) -> RechargeOrder:
        """创建充值订单。

        Args:
            account_id (UUID): 用户账户ID
            amount (int): 充值金额（单位：元）

        Returns:
            RechargeOrder: 创建的充值订单对象，包含订单号、金额等信息

        Raises:
            FailException: 当充值积分数量小于等于0时抛出异常

        """
        # 验证充值积分数量是否合法
        if amount <= 0:
            error_msg = "充值金额必须大于0"
            raise FailException(error_msg)

        # 根据金额计算需要支付的积分数量
        points_amount = RechargeOrder.calculate_points(amount)

        # 使用数据库事务创建订单
        with self.db.auto_commit():
            # 生成订单号：RE + 日期 + 随机8位字符
            order = RechargeOrder(
                order_no=f"RE{datetime.now(UTC).strftime('%Y%m%d')}{str(uuid.uuid4())[:8]}",
                account_id=account_id,  # 用户ID
                points_amount=points_amount,  # 充值积分数量
                amount=amount,  # 支付金额
                pay_status="UNPAID",  # 初始支付状态为未支付
            )
            # 将订单对象添加到数据库会话中
            self.db.session.add(order)

        # 返回创建的订单对象
        return order

    def confirm_recharge_order(
        self,
        order_id: UUID,
        pay_channel: str,
        pay_flow_no: str,
    ) -> None:
        """确认充值订单并增加用户积分。

        该方法用于处理已支付的充值订单，包括更新订单状态、增加用户积分和创建交易记录。
        所有操作都在数据库事务中执行，确保数据一致性。

        Args:
            order_id (UUID): 充值订单的唯一标识符
            pay_channel (str): 支付渠道，如"alipay"、"wechat"等
            pay_flow_no (str): 支付渠道返回的支付流水号

        Raises:
            FailException: 当订单不存在时抛出
            ValueError: 当订单状态不是未支付时抛出

        Returns:
            None

        """
        # 使用数据库事务确保操作的原子性
        with self.db.auto_commit():
            # 获取充值订单信息
            order = self.db.session.query(RechargeOrder).get(order_id)
            # 验证订单是否存在
            if not order:
                error_msg = "订单不存在"
                raise FailException(error_msg)
            # 验证订单状态，确保是未支付状态
            if order.pay_status != "UNPAID":
                error_msg = "订单已支付或取消，无法重复处理"
                raise ValueError(error_msg)

            # 更新订单支付状态和相关信息
            order.pay_status = "PAID"  # 标记为已支付
            order.pay_channel = pay_channel  # 记录支付渠道
            order.pay_time = datetime.now(UTC)  # 记录支付时间
            order.order_meta = {"pay_flow_no": pay_flow_no}  # 保存支付流水号

            # 查询用户的积分账户
            points_account = (
                self.db.session.query(AccountPoints)
                .filter(AccountPoints.account_id == order.account_id)
                .first()
            )
            # 如果用户没有积分账户，则创建新账户
            if not points_account:
                points_account = AccountPoints(account_id=order.account_id)
                self.db.session.add(points_account)
                self.db.session.flush()  # 刷新到数据库以获取ID

            # 增加用户积分余额
            points_account.total_points += order.points_amount  # 增加总积分
            points_account.available_points += order.points_amount  # 增加可用积分

            # 创建积分变动记录
            transaction = PointsTransaction(
                account_id=order.account_id,  # 用户ID
                transaction_type="RECHARGE",  # 交易类型：充值
                points_amount=order.points_amount,  # 积分变动数量（正数表示增加）
                order_id=order.id,  # 关联的订单ID
                transaction_desc=(
                    f"充值{order.points_amount}积分，支付金额{order.amount}元"
                ),  # 交易描述
                transaction_meta={  # 交易元数据
                    "order_no": order.order_no,  # 订单号
                    "pay_channel": pay_channel,  # 支付渠道
                },
            )
            # 保存积分变动记录
            self.db.session.add(transaction)
