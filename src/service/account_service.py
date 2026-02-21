import base64
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from flask import request
from flask_login import logout_user
from injector import inject
from redis import Redis

from pkg.password.password import compare_password, hash_password
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.exception.exception import FailException
from src.model.account import Account, AccountOAuth
from src.service.base_service import BaseService
from src.service.jwt_service import JwtService
from src.service.mail_service import MailService
from src.service.sms_service import SmsService


@inject
@dataclass
class AccountService(BaseService):
    db: SQLAlchemy
    jwt_service: JwtService
    redis_client: Redis
    sms_service: SmsService
    mail_service: MailService

    def get_account(self, account_id: UUID) -> Account:
        """通过账户ID获取账户信息

        Args:
            account_id (UUID): 账户的唯一标识符

        Returns:
            Account: 账户对象，如果不存在则返回None

        """
        return self.get(Account, account_id)

    def get_account_oauth_by_provider_name_and_openid(
        self,
        provider_name: str,
        openid: str,
    ) -> AccountOAuth:
        """通过OAuth提供商名称和openid获取账户OAuth信息

        Args:
            provider_name (str): OAuth提供商名称（如'google', 'github'等）
            openid (str): OAuth提供商返回的用户唯一标识

        Returns:
            AccountOAuth: 账户OAuth对象，如果不存在则返回None

        """
        return (
            self.db.session.query(AccountOAuth)
            .filter(
                AccountOAuth.provider == provider_name,
                AccountOAuth.openid == openid,
            )
            .one_or_none()
        )

    def get_account_by_email(self, email: str) -> Account:
        """通过邮箱地址获取账户信息

        Args:
            email (str): 账户的邮箱地址

        Returns:
            Account: 账户对象，如果不存在则返回None

        """
        return (
            self.db.session.query(Account)
            .filter(
                Account.email == email,
            )
            .one_or_none()
        )

    def get_account_by_phone(self, phone: str, code: str) -> Account:
        """通过手机号码获取账户信息

        Args:
            phone (str): 账户的手机号码
            code (str): 验证码

        Returns:
            Account: 账户对象，如果不存在则返回None

        """
        return (
            self.db.session.query(Account)
            .filter(
                Account.phone == phone,
            )
            .one_or_none()
        )

    def create_account(self, **kwargs: dict) -> Account:
        """创建新的账户

        Args:
            **kwargs: 创建账户所需的字段参数，如email、password等

        Returns:
            Account: 新创建的账户对象

        """
        return self.create(Account, **kwargs)

    def update_password(self, password: str, account: Account) -> Account:
        """更新账户密码。

        该方法实现了安全的密码更新机制，包括：
        1. 生成16字节的随机盐值
        2. 使用盐值对密码进行哈希处理
        3. 将哈希后的密码和盐值存储到数据库

        Args:
            password (str): 新的明文密码
            account (Account): 需要更新密码的账户对象

        Returns:
            Account: 更新后的账户对象，包含新的密码哈希值和盐值

        """
        # 生成16字节的随机盐值，用于增加密码哈希的安全性
        salt = secrets.token_bytes(16)
        # 将二进制盐值转换为base64编码的字符串，便于存储在数据库中
        base64_salt = base64.b64encode(salt).decode()

        # 使用盐值对密码进行哈希处理，增加密码破解难度
        password_hash = hash_password(password, salt)
        # 将二进制密码哈希值转换为base64编码的字符串，便于存储
        base64_password_hashed = base64.b64encode(password_hash).decode()

        # 调用update_account方法，更新账户的密码哈希值和盐值
        return self.update_account(
            account,
            password=base64_password_hashed,  # 更新哈希后的密码
            password_salt=base64_salt,  # 更新盐值
        )

    def update_account(self, account: Account, **kwargs: dict) -> Account:
        """更新账户信息

        Args:
            account (Account): 账户对象
            **kwargs: 更新账户所需的字段参数，如email、password等

        Returns:
            Account: 更新后的账户对象

        """
        return self.update(account, **kwargs)

    def password_login(self, email: str, password: str) -> dict[str, Any]:
        """处理用户密码登录。

        Args:
            email (str): 用户邮箱地址
            password (str): 用户密码

        Returns:
            dict[str, Any]: 包含访问令牌和过期时间的字典，格式为：
                {
                    "expire_at": int,  # 令牌过期时间戳
                    "access_token": str  # JWT访问令牌
                }

        Raises:
            UnauthorizedException: 当用户不存在或密码错误时抛出

        """
        # 根据邮箱获取账户信息
        account = self.get_account_by_email(email)
        # 检查账户是否存在
        if not account:
            error_msg = "用户不存在或密码错误"
            raise FailException(error_msg)

        # 验证密码是否已设置且密码是否正确
        if not account.is_password_set or not compare_password(
            password,
            account.password,
            account.password_salt,
        ):
            error_msg = "用户不存在或密码错误"
            raise FailException(error_msg)

        # 设置JWT令牌的过期时间为30天后
        expire_at = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
        # 构建JWT载荷，包含用户ID、发行者和过期时间
        payload = {
            "sub": str(account.id),  # 主题：账户ID
            "iss": "llmops",  # 发行者
            "exp": expire_at,  # 过期时间
        }
        # 使用JWT服务生成访问令牌
        access_token = self.jwt_service.generate_token(payload)

        # 更新账户的最后登录时间和IP地址
        self.update(
            account,
            last_login_at=datetime.now(UTC),
            last_login_ip=request.remote_addr,
        )

        # 在Redis中存储会话信息
        session_id = self._store_user_session(
            str(account.id),
            access_token,
            expire_at,
        )

        # 返回访问令牌、过期时间和用户ID
        return {
            "is_new_user": False,
            "expire_at": expire_at,
            "access_token": access_token,
            "user_id": str(account.id),
            "session_id": session_id,
        }

    def phone_number_login(self, phone: str, code: str) -> dict[str, Any]:
        verify_result = self.sms_service.verify_sms_code(phone, code)
        if not verify_result:
            error_msg = "验证码错误"
            raise FailException(error_msg)

        account = self.get_account_by_phone(phone)
        is_new_user = False
        if not account:
            is_new_user = True
            account = self.create_account(
                name="user_" + phone,
                email="",
                avatar="https://llmops-dev-1253877543.cos.ap-guangzhou.myqcloud.com/2026/02/20/efc213c0-3a5a-4ad1-8ca5-724ed1ee3ecd.png",
            )

        # 设置JWT令牌的过期时间为30天后
        expire_at = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
        # 构建JWT载荷，包含用户ID、发行者和过期时间
        payload = {
            "sub": str(account.id),  # 主题：账户ID
            "iss": "llmops",  # 发行者
            "exp": expire_at,  # 过期时间
        }
        # 使用JWT服务生成访问令牌
        access_token = self.jwt_service.generate_token(payload)

        # 更新账户的最后登录时间和IP地址
        self.update(
            account,
            last_login_at=datetime.now(UTC),
            last_login_ip=request.remote_addr,
        )

        # 在Redis中存储会话信息
        session_id = self._store_user_session(
            str(account.id),
            access_token,
            expire_at,
        )

        # 返回访问令牌、过期时间和用户ID
        return {
            "is_new_user": is_new_user,
            "expire_at": expire_at,
            "access_token": access_token,
            "user_id": str(account.id),
            "session_id": session_id,
        }

    def _generate_session_id(self) -> str:
        """生成唯一的会话ID

        Returns:
            str: 生成的会话ID

        """
        return str(uuid.uuid4())

    def _store_user_session(
        self,
        user_id: str,
        access_token: str,
        expire_at: int,
    ) -> str:
        """在Redis中存储用户会话信息

        Args:
            user_id: 用户ID
            access_token: 访问令牌
            expire_at: 令牌过期时间戳

        Returns:
            str: 会话ID

        """
        # 生成会话ID
        session_id = self._generate_session_id()

        # 计算过期时间（秒）
        expire_seconds = expire_at - int(datetime.now(UTC).timestamp())

        # 存储会话信息到Redis
        session_data = {
            "user_id": user_id,
            "access_token": access_token,
            "created_at": datetime.now(UTC).isoformat(),
            "last_accessed": datetime.now(UTC).isoformat(),
            "ip_address": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", ""),
        }

        # 使用Redis存储会话信息，键为session:{session_id}
        self.redis_client.setex(
            f"session:{session_id}",
            expire_seconds,
            json.dumps(
                session_data,
                ensure_ascii=False,
            ),
        )

        # 将会话ID添加到用户的会话列表中
        self.redis_client.sadd(f"user_sessions:{user_id}", session_id)
        self.redis_client.expireat(
            f"user_sessions:{user_id}",
            datetime.fromtimestamp(expire_at, UTC),
        )

        return session_id

    def logout(self, session_id: str) -> None:
        # 如果存在会话ID，从Redis中删除会话信息
        if session_id:
            # 获取会话信息
            session_data = self.redis_client.get(f"session:{session_id}")
            if session_data:
                session_info = json.loads(session_data)
                user_id = session_info.get("user_id")

                # 从用户的会话列表中移除当前会话ID
                if user_id:
                    self.redis_client.srem(f"user_sessions:{user_id}", session_id)

                # 删除会话数据
                self.redis_client.delete(f"session:{session_id}")

        # 清除用户会话信息，执行登出操作
        logout_user()

    def logout_all(self, user_id: str) -> None:
        # 获取用户的所有会话ID
        session_ids = self.redis_client.smembers(f"user_sessions:{user_id}")

        # 删除所有会话数据
        if session_ids:
            # 创建删除所有会话的管道
            pipe = self.redis_client.pipeline()

            # 删除每个会话数据
            for session_id in session_ids:
                pipe.delete(f"session:{session_id}")

            # 删除用户的会话列表
            pipe.delete(f"user_sessions:{user_id}")

            # 执行管道操作
            pipe.execute()

        # 清除用户会话信息，执行登出操作
        logout_user()

    def is_phone_number_bound(self, phone_number: str) -> bool:
        """检查手机号是否已被绑定

        Args:
            phone_number (str): 要检查的手机号码

        Returns:
            bool: 如果手机号已绑定返回True，否则返回False

        """
        account = self.get_account_by_phone(phone_number)
        return account is not None

    def is_email_bound(self, email: str) -> bool:
        """检查邮箱是否已被绑定到账户

        Args:
            email: 要检查的邮箱地址

        Returns:
            bool: 如果邮箱已被绑定返回True，否则返回False

        """
        account = self.get_account_by_email(email)
        return account is not None

    def bind_phone_number(self, phone_number: str, code: str) -> Account:
        """绑定手机号到账号

        Args:
            phone_number (str): 要绑定的手机号
            code (str): 短信验证码

        Returns:
            Account: 更新后的账号信息

        Raises:
            FailException: 当手机号已被其他账号绑定或验证码错误时抛出

        """
        # 检查手机号是否已被其他账号绑定
        account = self.get_account_by_phone(phone_number)
        if account:
            error_msg = "该手机号已绑定其他账号"
            raise FailException(error_msg)

        # 验证短信验证码是否正确
        verify_result = self.sms_service.verify_sms_code(phone_number, code)
        if not verify_result:
            error_msg = "验证码错误"
            raise FailException(error_msg)

        # 更新账号的手机号信息
        self.update_account(
            account,
            phone_number=phone_number,
        )
        return account

    def bind_email(self, email: str, code: str) -> Account:
        """绑定邮箱到当前账户。

        Args:
            email (str): 要绑定的邮箱地址
            code (str): 邮箱验证码

        Returns:
            Account: 更新后的账户对象

        Raises:
            FailException: 当邮箱已被其他账号绑定或验证码错误时抛出

        该方法会执行以下操作：
        1. 检查邮箱是否已被其他账号绑定
        2. 验证邮箱验证码是否正确
        3. 更新账户的邮箱信息
        4. 返回更新后的账户信息

        """
        # 根据邮箱获取账户信息，检查该邮箱是否已被其他账号绑定
        account = self.get_account_by_email(email)
        if account:
            # 如果邮箱已被绑定，抛出异常提示用户
            error_msg = "该邮箱已绑定其他账号"
            raise FailException(error_msg)

        # 验证用户输入的邮箱验证码是否正确
        verify_result = self.mail_service.verify_mail_code(email, code)
        if not verify_result:
            # 如果验证码错误，抛出异常提示用户
            error_msg = "验证码错误"
            raise FailException(error_msg)

        # 验证通过后，更新账户的邮箱信息
        self.update_account(
            account,
            email=email,
        )
        # 返回更新后的账户信息
        return account
