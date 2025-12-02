from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    """OAuth用户信息数据类

    用于存储从OAuth提供商获取的用户信息，包含以下字段：
    - id: 用户的唯一标识符
    - name: 用户姓名
    - email: 用户邮箱地址
    - avatar: 用户头像URL
    """

    id: str
    name: str
    email: str
    avatar: str


@dataclass
class OAuth(ABC):
    """OAuth认证抽象基类，定义了OAuth认证流程的基本接口"""

    client_id: str  # OAuth客户端ID
    client_secret: str  # OAuth客户端密钥
    redirect_uri: str  # OAuth回调地址

    @abstractmethod
    def get_provider(self) -> str:
        """获取OAuth提供商名称"""
        ...

    @abstractmethod
    def get_authorization_url(self) -> str:
        """获取OAuth授权URL"""
        ...

    @abstractmethod
    def get_access_token(self, code: str) -> str:
        """通过授权码获取访问令牌"""
        ...

    @abstractmethod
    def get_raw_user_info(self, access_token: str) -> dict:
        """通过访问令牌获取原始用户信息"""
        ...

    def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """获取标准化的用户信息

        Args:
            access_token: OAuth访问令牌

        Returns:
            OAuthUserInfo: 标准化的用户信息对象

        """
        raw_user_info = self.get_raw_user_info(access_token)

        return self._transform_user_info(raw_user_info)

    @abstractmethod
    def _transform_user_info(self, raw_user_info: dict) -> OAuthUserInfo:
        """将原始用户信息转换为标准化的OAuthUserInfo对象

        Args:
            raw_user_info: 从OAuth提供商获取的原始用户信息

        Returns:
            OAuthUserInfo: 标准化的用户信息对象

        """
        ...
