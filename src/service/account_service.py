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

    def get_account_by_phone(self, phone: str) -> Account:
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
                Account.phone_number == phone,
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

    def unbind_oauth_provider(self, provider_name: str, account: Account) -> Account:
        """解绑OAuth提供商

        Args:
            provider_name (str): OAuth提供商名称
            account (Account): 账户对象

        Returns:
            Account: 返回更新后的账户对象

        Raises:
            FailException: 当账户未绑定该OAuth提供商时抛出异常

        """
        # 查询账户的OAuth绑定信息
        account_oauth = (
            self.db.session.query(AccountOAuth)
            .filter(
                AccountOAuth.provider == provider_name,
                AccountOAuth.account_id == account.id,
            )
            .one_or_none()
        )
        # 检查是否存在OAuth绑定
        if account_oauth is None:
            error_msg = "该账户未绑定该OAuth提供商"
            raise FailException(error_msg)

        # 删除OAuth绑定记录
        self.delete(account_oauth)

        return account

    def password_bind_account(
        self,
        account: str,
        password: str,
        user_info: dict[str, Any],
        *,
        is_phone: bool = False,
    ) -> dict[str, Any]:
        """通过密码验证绑定OAuth账户。

        该方法用于处理用户通过密码验证后绑定OAuth账户的流程。包括验证用户身份、检查密码、
        确认OAuth绑定状态、生成JWT令牌以及创建用户会话等步骤。

        Args:
            account: 用户账户，可以是手机号或邮箱
            password: 用户密码
            user_info: OAuth用户信息字典，包含provider等字段
            is_phone: 是否使用手机号登录，默认为False（使用邮箱登录）

        Returns:
            包含以下键的字典：
            - is_new_user: 是否为新用户的布尔值
            - expire_at: JWT令牌过期时间戳
            - access_token: JWT访问令牌
            - user_id: 用户ID字符串
            - session_id: 会话ID字符串

        Raises:
            FailException: 当用户不存在、密码错误或OAuth已绑定时抛出

        """
        # 根据登录方式获取用户信息
        if is_phone:
            # 使用手机号获取账户
            user = self.get_account_by_phone(account)
        else:
            # 使用邮箱获取账户
            user = self.get_account_by_email(account)

        # 验证账户是否存在
        if not user:
            error_msg = "用户不存在或密码错误"
            raise FailException(error_msg)

        # 验证用户密码
        # 检查是否设置了密码以及密码是否正确
        if not user.is_password_set or not compare_password(
            password,
            user.password,
            user.password_salt,
        ):
            error_msg = "用户不存在或密码错误"
            raise FailException(error_msg)

        # 检查OAuth绑定状态
        # 查询是否已经绑定了相同的OAuth提供商
        existing_oauth = (
            self.db.session.query(AccountOAuth)
            .filter(
                AccountOAuth.account_id == user.id,
                AccountOAuth.provider == user_info.get("provider"),
            )
            .first()
        )

        # 如果已存在绑定，抛出异常
        if existing_oauth:
            error_msg = "该账户已绑定此OAuth提供商"
            raise FailException(error_msg)

        # 创建OAuth账户绑定
        self.create(
            AccountOAuth,
            account_id=user.id,
            provider=user_info.get("provider"),
            openid=user_info.get("id"),
            encrypted_token=user_info.get("encrypted_token"),
        )

        # 生成JWT令牌
        # 设置令牌有效期为30天
        expire_at = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
        # 构建JWT载荷信息
        payload = {
            "sub": str(user.id),  # 用户ID
            "iss": "llmops",  # 发行者标识
            "exp": expire_at,  # 过期时间戳
        }
        # 生成访问令牌
        access_token = self.jwt_service.generate_token(payload)

        # 准备更新数据
        update_data = {
            "last_login_at": datetime.now(UTC),
            "last_login_ip": request.remote_addr,
        }

        # 如果账户使用默认头像且OAuth提供了头像，则更新头像
        default_avatar = "https://llmops-dev-1253877543.cos.ap-guangzhou.myqcloud.com/2026/02/20/efc213c0-3a5a-4ad1-8ca5-724ed1ee3ecd.png"
        if user.avatar == default_avatar and user_info.get("avatar"):
            update_data["avatar"] = user_info.get("avatar")

        # 更新账户信息
        self.update(user, **update_data)

        # 存储用户会话信息
        # 在Redis中创建会话记录
        session_id = self._store_user_session(
            str(user.id),
            access_token,
            expire_at,
        )

        # 返回登录结果
        # 包含会话信息和用户标识
        return {
            "is_new_user": False,  # 非新用户标识
            "expire_at": expire_at,  # 令牌过期时间
            "access_token": access_token,  # JWT访问令牌
            "user_id": str(user.id),  # 用户ID
            "session_id": session_id,  # 会话ID
        }

    def password_login(
        self,
        account: str,
        password: str,
        *,
        is_phone: bool = False,
    ) -> dict[str, Any]:
        """处理用户密码登录。

        Args:
            account (str): 用户账号
            password (str): 用户密码
            is_phone (bool, optional): 是否使用手机号登录

        Returns:
            dict[str, Any]: 包含访问令牌和过期时间的字典，格式为：
                {
                    "expire_at": int,  # 令牌过期时间戳
                    "access_token": str  # JWT访问令牌
                }

        Raises:
            UnauthorizedException: 当用户不存在或密码错误时抛出

        """
        if is_phone:
            user = self.get_account_by_phone(account)
        else:
            # 根据邮箱获取账户信息
            user = self.get_account_by_email(account)
        # 检查账户是否存在
        if not user:
            error_msg = "用户不存在或密码错误"
            raise FailException(error_msg)

        # 验证密码是否已设置且密码是否正确
        if not user.is_password_set or not compare_password(
            password,
            user.password,
            user.password_salt,
        ):
            error_msg = "用户不存在或密码错误"
            raise FailException(error_msg)

        # 设置JWT令牌的过期时间为30天后
        expire_at = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
        # 构建JWT载荷，包含用户ID、发行者和过期时间
        payload = {
            "sub": str(user.id),  # 主题：账户ID
            "iss": "llmops",  # 发行者
            "exp": expire_at,  # 过期时间
        }
        # 使用JWT服务生成访问令牌
        access_token = self.jwt_service.generate_token(payload)

        # 更新账户的最后登录时间和IP地址
        self.update(
            user,
            last_login_at=datetime.now(UTC),
            last_login_ip=request.remote_addr,
        )

        # 在Redis中存储会话信息
        session_id = self._store_user_session(
            str(user.id),
            access_token,
            expire_at,
        )

        # 返回访问令牌、过期时间和用户ID
        return {
            "is_new_user": False,
            "expire_at": expire_at,
            "access_token": access_token,
            "user_id": str(user.id),
            "session_id": session_id,
        }

    def phone_number_bind_account(
        self,
        phone: str,
        code: str,
        user_info: dict[str, Any],
    ) -> dict[str, Any]:
        """通过手机号绑定OAuth账户。

        该方法用于将已注册的手机号账户与OAuth提供商进行绑定。流程包括：
        1. 验证短信验证码的有效性
        2. 检查手机号对应的账户是否存在
        3. 验证该账户是否已经绑定了相同的OAuth提供商
        4. 创建新的OAuth绑定记录
        5. 生成JWT访问令牌
        6. 更新账户的最后登录信息
        7. 在Redis中存储会话信息

        Args:
            phone (str): 要绑定的手机号码
            code (str): 短信验证码
            user_info (dict[str, Any]): OAuth相关信息，包含：
                - provider (str): OAuth提供商名称
                - openid (str): OAuth用户唯一标识
                - encrypted_token (str): 加密的OAuth令牌

        Returns:
            dict[str, Any]: 绑定结果信息，包含：
                - is_new_user (bool): 是否为新用户
                - expire_at (int): 令牌过期时间戳
                - access_token (str): JWT访问令牌
                - user_id (str): 用户ID
                - session_id (str): 会话ID

        Raises:
            FailException: 当验证码错误、手机号未注册或账户已绑定时抛出

        """
        # 验证短信验证码的有效性
        verify_result = self.sms_service.verify_sms_code(phone, code)
        if not verify_result:
            error_msg = "验证码错误"
            raise FailException(error_msg)

        # 根据手机号获取账户信息
        account = self.get_account_by_phone(phone)

        # 检查账户是否存在
        if not account:
            error_msg = "手机号未注册，请先注册"
            raise FailException(error_msg)

        # 检查是否已经绑定了该OAuth提供商
        existing_oauth = (
            self.db.session.query(AccountOAuth)
            .filter(
                AccountOAuth.account_id == account.id,
                AccountOAuth.provider == user_info.get("provider"),
            )
            .first()
        )

        # 如果已存在绑定，抛出异常
        if existing_oauth:
            error_msg = "该账户已绑定此OAuth提供商"
            raise FailException(error_msg)

        # 创建OAuth账户绑定
        self.create(
            AccountOAuth,
            account_id=account.id,
            provider=user_info.get("provider"),
            openid=user_info.get("id"),
            encrypted_token=user_info.get("encrypted_token"),
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

        # 准备更新数据
        update_data = {
            "last_login_at": datetime.now(UTC),
            "last_login_ip": request.remote_addr,
        }

        # 如果账户使用默认头像且OAuth提供了头像，则更新头像
        default_avatar = "https://llmops-dev-1253877543.cos.ap-guangzhou.myqcloud.com/2026/02/20/efc213c0-3a5a-4ad1-8ca5-724ed1ee3ecd.png"
        if account.avatar == default_avatar and user_info.get("avatar"):
            update_data["avatar"] = user_info.get("avatar")

        # 更新账户信息
        self.update(account, **update_data)

        # 在Redis中存储会话信息
        session_id = self._store_user_session(
            str(account.id),
            access_token,
            expire_at,
        )

        # 返回登录结果，包含新用户标识、过期时间、访问令牌、用户ID和会话ID
        return {
            "is_new_user": False,
            "expire_at": expire_at,
            "access_token": access_token,
            "user_id": str(account.id),
            "session_id": session_id,
        }

    def phone_number_login(self, phone: str, code: str) -> dict[str, Any]:
        """手机号登录功能。

        通过手机号和短信验证码进行登录验证。如果账户不存在则自动创建新账户。
        登录成功后生成JWT令牌并创建会话。

        Args:
            phone (str): 手机号码
            code (str): 短信验证码

        Returns:
            dict[str, Any]: 包含以下字段的字典：
                - is_new_user (bool): 是否为新用户
                - expire_at (int): 令牌过期时间戳
                - access_token (str): JWT访问令牌
                - user_id (str): 用户ID
                - session_id (str): 会话ID

        Raises:
            FailException: 当验证码错误时抛出

        """
        # 验证短信验证码的有效性
        verify_result = self.sms_service.verify_sms_code(phone, code)
        if not verify_result:
            error_msg = "验证码错误"
            raise FailException(error_msg)

        # 根据手机号获取账户信息
        account = self.get_account_by_phone(phone)
        is_new_user = False
        # 如果账户不存在，则创建新账户
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

        # 返回登录结果，包含新用户标识、过期时间、访问令牌、用户ID和会话ID
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

    def bind_phone_number(
        self,
        phone_number: str,
        code: str,
        account: Account,
    ) -> Account:
        """绑定手机号到账号

        Args:
            phone_number (str): 要绑定的手机号
            code (str): 短信验证码
            account (Account): 要绑定的账号

        Returns:
            Account: 更新后的账号信息

        Raises:
            FailException: 当手机号已被其他账号绑定或验证码错误时抛出

        """
        # 检查手机号是否已被其他账号绑定
        result = self.get_account_by_phone(phone_number)
        if result:
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

    def bind_email(self, email: str, code: str, account: Account) -> Account:
        """绑定邮箱到当前账户。

        Args:
            email (str): 要绑定的邮箱地址
            code (str): 邮箱验证码
            account (Account): 当前账户对象

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
        result = self.get_account_by_email(email)
        if result:
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
