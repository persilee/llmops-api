import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from injector import inject
from sqlalchemy import Date, cast, extract, func

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.entity.points_entity import DeductFromText
from src.exception.exception import FailException
from src.model.account import Account
from src.model.account_points import AccountPoints, PointsTransaction
from src.model.recharge_order import RechargeOrder
from src.service.base_service import BaseService

logger = logging.getLogger(__name__)


@inject
@dataclass
class PointsService(BaseService):
    db: SQLAlchemy

    def get_points_by_account_id(self, account: Account) -> AccountPoints:
        """根据用户id获取用户积分

        Args:
            account (Account): 用户

        Returns:
            AccountPoints: 用户积分

        """
        points = (
            self.db.session.query(AccountPoints)
            .filter(AccountPoints.account_id == account.id)
            .one_or_none()
        )
        if points is None:
            error_msg = "用户积分不存在"
            raise FailException(error_msg)

        return points

    def deduct_points_by_token(
        self,
        account_id: UUID,
        token_count: int,
        deduct_from: str,
        message_id: UUID | None = None,
        app_id: UUID | None = None,
    ) -> None:
        """根据token消耗扣除用户积分

        Args:
            account_id (UUID): 用户账户ID
            message_id (UUID): 消息ID，用于关联积分交易记录
            deduct_from (str): 积分扣除来源
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

                # 积分消耗来源文本
                deduct_from_text = DeductFromText.MAP.get(deduct_from, "")
                # 记录积分变动
                try:
                    transaction = PointsTransaction(
                        account_id=account_id,
                        transaction_type="DEDUCT",
                        points_amount=-deduct_points,  # 负数表示扣除
                        token_amount=token_count,
                        deduct_from=deduct_from,  # 消耗的token来源
                        message_id=message_id,
                        app_id=app_id,
                        transaction_desc=f"{deduct_from_text}消耗{token_count}token，扣除{deduct_points}积分",
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

    def get_monthly_deduct_points(
        self,
        account_id: UUID | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> dict[str, Decimal]:
        """按月度统计积分消耗情况

        Args:
            account_id: 可选，指定用户ID，为空则统计所有用户
            year: 可选，指定年份，为空则统计当前年
            month: 可选，指定月份，为空则统计指定年的所有月份

        Returns:
            月度消耗统计字典，格式：{"YYYY-MM": 消耗积分总量, ...}

        Example:
            {
                "2024-01": Decimal("150.50"),
                "2024-02": Decimal("200.75")
            }

        """
        # 构建查询
        query = self.db.session.query(
            extract("year", PointsTransaction.created_at).label("year"),
            extract("month", PointsTransaction.created_at).label("month"),
            func.abs(func.sum(PointsTransaction.points_amount)).label("total_deduct"),
        ).filter(
            PointsTransaction.transaction_type == "DEDUCT",  # 只统计扣除类型
        )

        # 过滤指定用户
        if account_id:
            query = query.filter(PointsTransaction.account_id == account_id)

        # 过滤指定年份
        current_year = datetime.now(UTC).year
        target_year = year or current_year
        query = query.filter(
            extract("year", PointsTransaction.created_at) == target_year,
        )

        # 过滤指定月份
        if month:
            query = query.filter(
                extract("month", PointsTransaction.created_at) == month,
            )

        # 按年月分组
        query = query.group_by("year", "month").order_by("year", "month")

        # 执行查询并格式化结果
        results = query.all()
        monthly_stats = {}
        for result in results:
            month_key = f"{int(result.year)}-{int(result.month):02d}"
            monthly_stats[month_key] = result.total_deduct or Decimal("0.00")

        return monthly_stats

    def get_points_by_date_range(
        self,
        start_date: date,
        end_date: date,
        account: Account,
        *,
        include_details: bool = False,
    ) -> dict[str, any]:
        """按日期范围查询积分情况

        Args:
            start_date: 开始日期（包含）
            end_date: 结束日期（包含）
            account: 账户
            include_details: 是否返回详细交易记录，默认False

        Returns:
            积分统计结果，包含总量和可选的明细

        Example:
            {
                "total_deduct": Decimal("350.25"),
                "transaction_count": 15,
                "details": [
                    {
                        "id": "uuid",
                        "account_id": "uuid",
                        "points_amount": Decimal("-50.00"),
                        "token_amount": 50000,
                        "created_at": "2024-03-15T10:30:00",
                        "transaction_desc": "抵扣消息token消耗50000token，扣除50.00积分"
                    },
                    ...
                ]
            }

        """
        # 基础过滤条件
        filters = [
            cast(PointsTransaction.created_at, Date) >= start_date,
            cast(PointsTransaction.created_at, Date) <= end_date,
        ]

        # 过滤指定用户
        if account.id:
            filters.append(PointsTransaction.account_id == account.id)

        # 构建总量查询
        total_query = self.db.session.query(
            func.abs(func.sum(PointsTransaction.points_amount)).label("total_deduct"),
            func.count(PointsTransaction.id).label("transaction_count"),
        ).filter(*filters)

        total_result = total_query.one()
        total_deduct = total_result.total_deduct or Decimal("0.00")
        transaction_count = total_result.transaction_count or 0

        # 构建返回结果
        result = {"total_deduct": total_deduct, "transaction_count": transaction_count}

        # 如果需要返回明细
        if include_details:
            detail_query = self.db.session.query(PointsTransaction).filter(*filters)
            # 按创建时间倒序
            detail_query = detail_query.order_by(PointsTransaction.created_at.desc())

            # 格式化明细数据
            details = [
                {
                    "id": str(trans.id),
                    "app_name": trans.app.name,
                    "app_icon": trans.app.icon,
                    "account_id": str(trans.account_id),
                    "points_amount": trans.points_amount,
                    "token_amount": trans.token_amount,
                    "message_id": str(trans.message_id) if trans.message_id else None,
                    "app_id": str(trans.app_id) if trans.app_id else None,
                    "transaction_desc": trans.transaction_desc,
                    "created_at": trans.created_at.isoformat(),
                    "transaction_meta": trans.transaction_meta,
                }
                for trans in detail_query.all()
            ]
            result["details"] = details

        return result
