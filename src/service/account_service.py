import base64
import secrets
from dataclasses import dataclass
from uuid import UUID

from injector import inject

from pkg.password.password import hash_password
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.model.account import Account, AccountOAuth
from src.service.base_service import BaseService


@inject
@dataclass
class AccountService(BaseService):
    db: SQLAlchemy

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
