import json
import os
import secrets
import string
from datetime import UTC, datetime, timedelta

from alibabacloud_dypnsapi20170525 import models as dypnsapi_20170525_models
from alibabacloud_dypnsapi20170525.client import Client as Dypnsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from injector import inject
from redis import Redis
from sqlalchemy import desc

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.exception.exception import FailException
from src.model.account import VerificationCode
from src.service.base_service import BaseService


@inject
class SmsService(BaseService):
    redis_client: Redis
    db: SQLAlchemy

    def __init__(self, redis_client: Redis, db: SQLAlchemy) -> None:
        self.redis_client = redis_client
        self.db = db
        sms_config = open_api_models.Config(
            access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        )
        sms_config.endpoint = os.getenv("ALIBABA_CLOUD_ENDPOINT")
        self.client = Dypnsapi20170525Client(sms_config)

    def generate_verification_code(self, length=6) -> str:
        """生成6位数字验证码"""
        return "".join(secrets.choice(string.digits) for _ in range(length))

    def send_sms_verify_code(self, phone_number) -> str:
        """发送短信验证码"""
        if self.redis_client.exists(f"sms_limit:{phone_number}"):
            error_msg = "验证码发送过于频繁，请稍后再试"
            raise FailException(error_msg)

        # 生成验证码
        verify_code = self.generate_verification_code()

        # 构造请求参数
        send_sms_verify_code_request = (
            dypnsapi_20170525_models.SendSmsVerifyCodeRequest(
                phone_number=phone_number,
                sign_name="速通互联验证码",
                template_code="100001",
                template_param=json.dumps({"code": verify_code, "min": "5"}),
            )
        )

        try:
            # 发送短信验证码
            self.client.send_sms_verify_code(send_sms_verify_code_request)

            self.create(
                VerificationCode,
                account=phone_number,
                code=verify_code,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )

            # 设置发送限制（60秒）
            self.redis_client.setex(f"sms_limit:{phone_number}", "1", 60)
        except Exception as e:
            error_msg = f"验证码发送失败: {e!s}"
            raise FailException(error_msg) from e
        else:
            return verify_code

    def verify_sms_code(self, phone_number, verify_code) -> bool:
        """验证短信验证码"""
        code_record = (
            self.db.session.query(VerificationCode)
            .filter_by(
                account=phone_number,
                code=verify_code,
                used=False,
            )
            .order_by(desc(VerificationCode.created_at))
            .first()
        )

        if not code_record:
            error_msg = "验证码错误或不存在"
            raise FailException(error_msg)

        if not code_record.is_valid():
            error_msg = "验证码已过期"
            raise FailException(error_msg)

        code_record.mark_as_used()

        # 验证成功后删除验证码
        self.redis_client.delete(f"sms_limit:{phone_number}")

        return True
