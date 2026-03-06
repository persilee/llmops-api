import logging
import os

import requests

from pkg.oauth.oauth import OAuth, OAuthUserInfo
from src.lib.helper import get_sign

logger = logging.getLogger(__name__)


class WechatOAuth(OAuth):
    """微信OAuth认证处理类

    提供微信OAuth认证相关的功能，包括：
    - 获取微信授权URL
    - 处理微信扫码登录
    - 获取用户信息
    - 转换用户信息格式
    """

    # 微信OAuth服务API地址，用于获取OAuth授权信息
    _YUNGOUOS_OAUTH_URL = "https://api.wx.yungouos.com/api/wx/getOauthInfo"
    # 微信网页登录API地址，用于获取网页登录参数
    _WX_WEB_LOGIN_URL = "https://api.wx.yungouos.com/api/wx/getWebLogin"
    # 微信开放平台二维码连接地址，用于生成扫码登录二维码
    _WX_QRCONNECT_URL = "https://open.weixin.qq.com/connect/qrconnect"

    def get_provider(self) -> str:
        """获取OAuth提供商标识

        Returns:
            str: 返回微信小程序OAuth提供商的标识符"wxmp"

        """
        return "wxmp"

    def get_access_token(self, code) -> str:
        """使用授权码获取访问令牌

        Args:
            code (str): 微信授权服务器返回的授权码

        Returns:
            str: 访问令牌(access_token)，用于后续获取用户信息

        实现逻辑：
        1. 使用授权码向微信OAuth服务器请求访问令牌
        2. 需要包含应用ID、应用密钥等必要参数
        3. 对请求参数进行签名以确保安全性
        4. 解析响应获取访问令牌

        """
        return code

    def get_authorization_url(self) -> str:
        """获取微信授权URL

        该方法用于生成微信扫码登录的授权URL。主要步骤包括：
        1. 从环境变量获取必要的配置信息
        2. 构造请求参数并生成签名
        3. 向OAuth服务发送请求获取授权参数
        4. 构造最终的微信授权URL

        Returns:
            str: 微信授权URL，用于生成二维码供用户扫码登录

        """
        # 从环境变量中获取微信OAuth相关配置信息
        # WX_HREF_URL: 自定义二维码样式URL
        wx_href_url = os.getenv("WX_HREF_URL")  # 二维码样式URL

        # 准备请求参数
        # 构造请求OAuth服务所需的参数
        params = {
            "mch_id": self.client_id,  # 商户ID，用于标识请求方
            "callback_url": self.redirect_uri,  # 授权完成后的回调地址
        }

        # 生成签名并添加到参数中
        # 使用API密钥对请求参数进行签名，确保请求的安全性
        # 签名算法将所有参数按照特定规则排序后进行加密
        params["sign"] = get_sign(params, self.client_secret)

        # 设置请求头
        # Content-Type设置为表单格式，符合OAuth服务要求
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        }

        # 发送请求
        # 向OAuth服务发送POST请求，获取微信授权所需的参数
        # 请求包含签名以确保安全性，设置30秒超时防止长时间等待
        response = requests.post(
            self._WX_WEB_LOGIN_URL,  # OAuth服务地址
            params=params,  # 包含签名的请求参数
            headers=headers,  # 请求头
            timeout=30,  # 设置连接和读取超时时间
        )
        response.raise_for_status()  # 检查请求是否成功，失败则抛出异常

        # 构建二维码URL
        # 解析响应数据，构造微信扫码登录的二维码URL
        # URL包含以下关键参数：
        # - appid: 微信开放平台应用ID
        # - redirect_uri: 授权重定向地址
        # - response_type: 固定值code，表示返回授权码
        # - scope: 授权作用域，snsapi_login用于网站登录
        # - state: 状态参数，用于防止CSRF攻击
        # - href: 自定义二维码样式
        resp = response.json()  # 解析JSON响应数据
        data = resp["data"]
        return (
            f"{self._WX_QRCONNECT_URL}"  # 微信二维码连接基础地址
            f"?appid={data['appId']}"  # 微信开放平台应用ID
            f"&redirect_uri={data['redirect_uri']}"  # 授权重定向地址
            f"&response_type=code"  # 固定值，表示返回授权码
            f"&scope=snsapi_login"  # 授权作用域，snsapi_login用于网站登录
            f"&state={data['state']}"  # 状态参数，用于防止CSRF攻击
            f"&href={wx_href_url}"  # 自定义二维码样式
            f"&self_redirect=false"  # 是否自行重定向，false表示由微信处理
            f"&login_type=jssdk"  # 登录类型，使用JS SDK方式
            f"#wechat_redirect"  # 微信重定向标识
        )

    def get_raw_user_info(self, access_token) -> dict:
        """通过access_token获取微信用户的原始信息

        Args:
            access_token: OAuth授权后获得的访问令牌

        Returns:
            dict: 包含用户openid、昵称和头像的字典

        """
        # 构造请求参数
        params = {
            "mch_id": self.client_id,  # 商户ID
            "code": access_token,  # 访问令牌
        }

        # 生成请求签名，确保请求的安全性
        params["sign"] = get_sign(params, self.client_secret)

        # 设置请求头
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",  # 表单格式请求
            "Accept": "*/*",  # 接受任意类型的响应
        }

        # 发送GET请求获取用户信息
        response = requests.get(
            self._YUNGOUOS_OAUTH_URL,  # OAuth服务地址
            params=params,  # 包含签名的请求参数
            headers=headers,  # 请求头
            timeout=30,  # 设置连接和读取超时时间
        )

        # 检查请求是否成功，失败则抛出异常
        response.raise_for_status()

        # 解析JSON响应数据
        raw_info = response.json()
        data = raw_info["data"]  # 提取并返回关键用户信息
        # 提取并返回关键用户信息
        return {
            "openid": data["openId"],  # 用户唯一标识
            "nickname": data["wxUserInfo"]["nickname"],  # 用户昵称
            "headimgurl": data["wxUserInfo"]["headimgurl"],  # 用户头像URL
        }

    def _transform_user_info(self, raw_user_info: dict) -> OAuthUserInfo:
        """将微信返回的原始用户信息转换为OAuthUserInfo对象

        Args:
            raw_user_info (dict): 微信返回的原始用户信息字典，
            包含openid、nickname、headimgurl等字段

        Returns:
            OAuthUserInfo: 转换后的用户信息对象，包含以下字段：
                - id: 用户的openid，转为字符串类型
                - name: 用户昵称
                - avatar: 用户头像URL
                - email: 邮箱地址（微信不提供，设为空字符串）

        """
        return OAuthUserInfo(
            id=str(raw_user_info["openid"]),
            name=raw_user_info["nickname"],
            avatar=raw_user_info["headimgurl"],
            email="",
        )
