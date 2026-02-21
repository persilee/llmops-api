import os
import secrets
import string
from datetime import UTC, datetime, timedelta

from alibabacloud_dm20151123 import models as dm_20151123_models
from alibabacloud_dm20151123.client import Client as Dm20151123Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from injector import inject
from redis import Redis
from sqlalchemy import desc

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.exception.exception import FailException
from src.model.account import VerificationCode
from src.service.base_service import BaseService


@inject
class MailService(BaseService):
    redis_client: Redis
    db: SQLAlchemy

    def __init__(self, redis_client: Redis, db: SQLAlchemy) -> None:
        # 初始化Redis客户端，用于缓存和限流
        self.redis_client = redis_client
        # 初始化数据库连接，用于存储验证码记录
        self.db = db
        # 创建阿里云邮件服务配置对象
        mail_config = open_api_models.Config(
            # 从环境变量获取访问密钥ID
            access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            # 从环境变量获取访问密钥Secret
            access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        )
        # 设置阿里云邮件服务的端点地址
        mail_config.endpoint = os.getenv("ALIBABA_CLOUD_EMAIL_ENDPOINT")
        # 创建阿里云邮件服务客户端实例
        self.client = Dm20151123Client(mail_config)

    def generate_verification_code(self, length=6) -> str:
        """生成6位数字验证码"""
        return "".join(secrets.choice(string.digits) for _ in range(length))

    def send_mail_verify_code(self, email: str) -> str:
        """发送邮箱验证码

        Args:
            email (str): 接收验证码的邮箱地址

        Returns:
            str: 生成的6位验证码

        Raises:
            FailException: 当验证码发送过于频繁或发送失败时抛出

        Note:
            - 验证码有效期为5分钟
            - 同一邮箱60秒内只能发送一次验证码
            - 使用阿里云邮件服务发送验证码

        """
        # 检查Redis中是否存在该邮箱的发送限制记录
        if self.redis_client.exists(f"mail_limit:{email}"):
            error_msg = "验证码发送过于频繁，请稍后再试"
            raise FailException(error_msg)

        # 生成6位随机验证码
        verify_code = self.generate_verification_code()

        # 构建阿里云邮件服务请求对象
        send_mail_verify_code_request = dm_20151123_models.SingleSendMailRequest(
            account_name=os.getenv(
                "ALIBABA_CLOUD_EMAIL_ACCOUNT_NAME",
            ),  # 发件人邮箱地址
            address_type=1,  # 1为发信人地址，0为回信地址
            reply_to_address=False,  # 不使用回信地址
            subject="虎子 · 邮箱验证码",  # 邮件主题
            to_address=email,  # 收件人邮箱
            text_body=(  # 邮件正文内容
                f"你的验证码是 {verify_code}， 该验证码 5 分钟内有效，请勿泄露给他人"
            ),
        )

        # 创建运行时选项对象
        runtime = util_models.RuntimeOptions()
        try:
            # 调用阿里云邮件服务发送验证码邮件
            self.client.single_send_mail_with_options(
                send_mail_verify_code_request,
                runtime,
            )
            # 将验证码信息保存到数据库
            self.create(
                VerificationCode,
                account=email,  # 邮箱账号
                code=verify_code,  # 验证码
                expires_at=datetime.now(UTC) + timedelta(minutes=5),  # 设置5分钟后过期
            )

            # 在Redis中设置60秒的发送限制
            self.redis_client.setex(f"mail_limit:{email}", "1", 60)
        except Exception as e:
            # 如果发送过程中出现异常，抛出业务异常
            error_msg = f"验证码发送失败: {e!s}"
            raise FailException(error_msg) from e
        else:
            # 发送成功，返回验证码
            return verify_code

    def verify_mail_code(self, email, verify_code) -> bool:
        """验证邮箱验证码

        Args:
            email (str): 待验证的邮箱地址
            verify_code (str): 用户输入的验证码

        Returns:
            bool: 验证成功返回True

        Raises:
            FailException: 当验证码不存在、错误或已过期时抛出异常

        """
        # 查询最新的未使用的验证码记录
        code_record = (
            self.db.session.query(VerificationCode)
            .filter_by(
                account=email,
                code=verify_code,
                used=False,
            )
            .order_by(desc(VerificationCode.created_at))
            .first()
        )

        # 检查验证码是否存在
        if not code_record:
            error_msg = "验证码错误或不存在"
            raise FailException(error_msg)

        # 检查验证码是否过期
        if not code_record.is_valid():
            error_msg = "验证码已过期"
            raise FailException(error_msg)

        # 标记验证码为已使用
        code_record.mark_as_used()

        # 验证成功后删除Redis中的邮件发送限制记录
        self.redis_client.delete(f"mail_limit:{email}")

        return True
