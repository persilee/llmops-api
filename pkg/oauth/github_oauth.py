import logging
import urllib

import requests

from pkg.oauth.oauth import OAuth, OAuthUserInfo

logger = logging.getLogger(__name__)


class GithubOAuth(OAuth):
    """GitHub OAuth认证实现类

    提供GitHub OAuth认证相关的功能，包括获取授权URL、访问令牌和用户信息等。
    """

    _AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    _ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
    _USER_INFO_URL = "https://api.github.com/user"
    _EMAIL_INFO_URL = "https://api.github.com/user/emails"

    def get_provider(self) -> str:
        """获取OAuth提供商名称

        Returns:
            str: 返回固定的提供商名称"github"

        """
        return "github"

    def get_authorization_url(self) -> str:
        """获取GitHub OAuth授权URL

        构建并返回用于GitHub OAuth授权的完整URL，包含必要的参数。

        Returns:
            str: 完整的授权URL

        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
        }

        return self._AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)

    def get_access_token(self, code: str) -> str:
        """使用授权码获取访问令牌

        Args:
            code (str): OAuth授权流程中获得的授权码

        Returns:
            str: GitHub的访问令牌

        Raises:
            ValueError: 当获取访问令牌失败时抛出

        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        headers = {"Accept": "application/json"}

        resp = requests.post(
            self._ACCESS_TOKEN_URL,
            data=data,
            headers=headers,
            timeout=(5, 10),
        )
        resp.raise_for_status()
        resp_json = resp.json()

        access_token = resp_json.get("access_token")
        if not access_token:
            error_msg = f"Github OAuth 授权失败: {resp_json}"
            raise ValueError(error_msg)

        return access_token

    def get_raw_user_info(self, access_token: str) -> dict:
        """获取原始用户信息

        使用访问令牌获取GitHub用户的基本信息和邮箱信息。

        Args:
            access_token (str): GitHub的访问令牌

        Returns:
            dict: 包含用户信息的字典，合并了基本信息和主邮箱

        """
        headers = {"Authorization": f"token {access_token}"}

        resp = requests.get(self._USER_INFO_URL, headers=headers, timeout=(5, 10))
        resp.raise_for_status()
        raw_info = resp.json()

        email_resp = requests.get(
            self._EMAIL_INFO_URL,
            headers=headers,
            timeout=(5, 10),
        )
        email_resp.raise_for_status()
        email_info = email_resp.json()
        primary_email = next(
            (email for email in email_info if email.get("primary", None)),
            None,
        )

        logger.info("Github OAuth 用户信息: %s", raw_info)

        return {**raw_info, "email": primary_email.get("email", None)}

    def _transform_user_info(self, raw_user_info: dict) -> OAuthUserInfo:
        """转换用户信息为标准格式

        将从GitHub获取的原始用户信息转换为标准的OAuthUserInfo格式。
        如果用户没有公开邮箱，则生成一个虚拟邮箱。

        Args:
            raw_user_info (dict): 原始用户信息字典

        Returns:
            OAuthUserInfo: 标准格式的用户信息对象

        """
        email = raw_user_info.get("email")
        if not email:
            email = (
                f"{raw_user_info['id']}{raw_user_info.get('login')}"
                "@user.no-reply@github.com"
            )

        return OAuthUserInfo(
            id=str(raw_user_info.get("id")),
            name=str(raw_user_info.get("name")),
            email=str(email),
            avatar=str(raw_user_info.get("avatar_url")),
        )
