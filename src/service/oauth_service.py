import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import request
from injector import inject

from pkg.oauth.github_oauth import GithubOAuth
from pkg.oauth.oauth import OAuth
from pkg.oauth.wechat_oauth import WechatOAuth
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.exception.exception import NotFoundException
from src.model.account import AccountOAuth
from src.service.account_service import AccountService
from src.service.base_service import BaseService
from src.service.jwt_service import JwtService


@inject
@dataclass
class OAuthService(BaseService):
    db: SQLAlchemy
    account_service: AccountService
    jwt_service: JwtService

    @classmethod
    def get_all_oauth(cls) -> dict[str, OAuth]:
        """获取所有OAuth提供商配置

        Returns:
            dict[str, OAuth]: 返回包含所有OAuth提供商的字典，
            键为提供商名称，值为OAuth实例

        """
        # 创建GitHub OAuth实例
        # 从环境变量中获取GitHub OAuth所需的配置信息
        github = GithubOAuth(
            client_id=os.getenv("GITHUB_CLIENT_ID"),  # GitHub应用的客户端ID
            client_secret=os.getenv("GITHUB_CLIENT_SECRET"),  # GitHub应用的客户端密钥
            redirect_uri=os.getenv("GITHUB_REDIRECT_URL"),  # OAuth回调URL
        )

        wechat = WechatOAuth(
            client_id=os.getenv("YUNGOUOS_MCH_ID"),
            client_secret=os.getenv("YUNGOUOS_KEY"),
            redirect_uri=os.getenv("WX_CALLBACK_URL"),
        )

        # 返回包含所有OAuth提供商的字典
        return {"github": github, "wxmp": wechat}

    @classmethod
    def get_oauth_by_provider_name(cls, provider_name: str) -> OAuth:
        """根据提供商名称获取OAuth实例

        Args:
            provider_name (str): OAuth提供商名称

        Returns:
            OAuth: 对应的OAuth实例

        Raises:
            NotFoundException: 当指定的OAuth提供商不存在时抛出

        """
        # 获取所有已配置的OAuth提供商
        all_oauth = cls.get_all_oauth()
        # 根据提供商名称查找对应的OAuth实例
        oauth = all_oauth.get(provider_name)

        # 如果找不到对应的OAuth实例，抛出异常
        if oauth is None:
            error_msg = f"授权提供商 {provider_name} 不存在"
            raise NotFoundException(error_msg)

        # 返回找到的OAuth实例
        return oauth

    def auth_login_create(self, provider_info: dict[str, Any]) -> dict[str, Any]:
        """创建新的OAuth登录账户并生成访问令牌。

        使用OAuth提供商返回的用户信息创建新账户，建立OAuth账户绑定关系，
        并生成JWT访问令牌用于后续认证。

        Args:
            provider_info (dict[str, Any]): OAuth提供商返回的用户信息字典，包含：
                - name (str): 用户名
                - email (str): 邮箱地址
                - avatar (str): 头像URL
                - provider (str): OAuth提供商名称
                - id (str): OAuth提供商返回的用户唯一标识
                - encrypted_token (str): 加密后的访问令牌

        Returns:
            dict[str, Any]: 包含认证信息的字典，包含：
                - expire_at (int): JWT令牌过期时间（Unix时间戳）
                - access_token (str): JWT访问令牌
                - is_new_user (bool): 标记是否为新用户（固定为False）

        """
        # 准备账户创建数据
        account_data = {
            "name": provider_info.get("name"),
            "email": provider_info.get("email"),
            "avatar": provider_info.get("avatar"),
            "last_login_at": datetime.now(UTC),
            "last_login_ip": request.remote_addr,
        }

        # 创建新账户
        account = self.account_service.create_account(**account_data)
        # 新用户，赠送1000积分
        self.account_service.create_account_point(account.id, 1000)

        # 创建OAuth账户绑定记录，将新账户与OAuth提供商关联
        self.create(
            AccountOAuth,  # OAuth账户模型
            account_id=account.id,  # 关联的账户ID
            provider=provider_info.get("provider"),  # OAuth提供商名称
            openid=provider_info.get("id"),  # OAuth提供商返回的用户唯一标识
            encrypted_token=provider_info.get("encrypted_token"),  # 加密后的访问令牌
        )

        # 设置JWT令牌的过期时间为30天后
        expire_at = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
        # 构建JWT载荷，包含必要的认证信息
        payload = {
            "sub": str(account.id),  # 主题：账户ID，转换为字符串格式
            "iss": "llmops",  # 发行者：系统标识
            "exp": expire_at,  # 过期时间：Unix时间戳格式
        }
        # 使用JWT服务生成访问令牌
        access_token = self.jwt_service.generate_token(payload)

        # 返回认证信息，包括访问令牌和过期时间
        return {
            "expire_at": expire_at,  # 令牌过期时间
            "access_token": access_token,  # JWT访问令牌
            "is_new_user": False,  # 标记是否为新用户
        }

    def oauth_login(
        self,
        provider_name: str,
        code: str,
    ) -> dict[str, Any]:
        """处理OAuth登录流程

        Args:
            provider_name (str): OAuth提供商名称
            code (str): OAuth授权码

        Returns:
            dict: 包含访问令牌和过期时间的字典

        """
        # 获取指定OAuth提供商的配置
        oauth = self.get_oauth_by_provider_name(provider_name)

        # 使用授权码获取访问令牌
        oauth_access_token = oauth.get_access_token(code)

        # 使用访问令牌获取用户信息
        oauth_user_info = oauth.get_user_info(oauth_access_token)

        # 查找是否已存在该OAuth账户绑定
        account_oauth = (
            self.account_service.get_account_oauth_by_provider_name_and_openid(
                provider_name,
                oauth_user_info.id,
            )
        )

        # 如果不存在OAuth账户绑定，则创建新账户或绑定到现有账户
        if not account_oauth:
            # 尝试通过邮箱查找现有账户
            account = None
            if oauth_user_info.email:
                account = self.account_service.get_account_by_email(
                    oauth_user_info.email,
                )

            if not account:
                # 如果账户不存在，返回用户信息
                return {
                    "provider_info": {
                        "id": oauth_user_info.id,
                        "name": oauth_user_info.name,
                        "email": oauth_user_info.email,
                        "avatar": oauth_user_info.avatar,
                        "provider": provider_name,
                        "encrypted_token": oauth_access_token,
                    },
                    "is_new_user": True,
                }

            # 创建OAuth账户绑定
            account_oauth = self.create(
                AccountOAuth,
                account_id=account.id,
                provider=provider_name,
                openid=oauth_user_info.id,
                encrypted_token=oauth_access_token,
            )
        else:
            # 如果已存在OAuth绑定，获取关联的账户信息
            account = self.account_service.get_account(account_oauth.account_id)

        # 更新账户的最后登录时间和IP地址
        self.update(
            account,
            last_login_at=datetime.now(UTC),
            last_login_ip=request.remote_addr,
        )

        # 更新OAuth账户的访问令牌
        self.update(
            account_oauth,
            encrypted_token=oauth_access_token,
        )

        # 设置JWT令牌的过期时间为30天后
        expire_at = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
        # 构建JWT载荷
        payload = {
            "sub": str(account.id),  # 主题：账户ID
            "iss": "llmops",  # 发行者
            "exp": expire_at,  # 过期时间
        }
        # 生成JWT访问令牌
        access_token = self.jwt_service.generate_token(payload)

        # 返回访问令牌和过期时间
        return {
            "expire_at": expire_at,
            "access_token": access_token,
            "is_new_user": False,
        }
