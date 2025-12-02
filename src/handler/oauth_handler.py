from dataclasses import dataclass

from flasgger import swag_from
from injector import inject

from pkg.response.response import Response, success_json, validate_error_json
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.oauth_schema import AuthorizeReq, AuthorizeResp
from src.service.oauth_service import OAuthService


@inject
@dataclass
class OAuthHandler:
    oauth_service: OAuthService

    @route("/<string:provider_name>", methods=["GET"])
    @swag_from(get_swagger_path("oauth_handler/provider.yaml"))
    def provider(self, provider_name: str) -> Response:
        """处理OAuth认证请求

        Args:
            provider_name (str): OAuth提供商名称，如'google'、'github'等

        Returns:
            Response: 包含重定向URL的JSON响应

        功能说明：
            1. 根据提供商名称获取对应的OAuth服务实例
            2. 生成授权URL
            3. 返回包含重定向URL的成功响应

        """
        oauth = self.oauth_service.get_oauth_by_provider_name(provider_name)

        redirect_url = oauth.get_authorization_url()

        return success_json({"redirect_url": redirect_url})

    @route("/authorize/<string:provider_name>", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/authorize.yaml"))
    def authorize(self, provider_name: str) -> Response:
        """处理OAuth授权回调

        Args:
            provider_name (str): OAuth提供商名称，如'google'、'github'等

        Returns:
            Response: 包含用户凭证信息的JSON响应

        功能说明：
            1. 验证请求数据
            2. 使用授权码进行OAuth登录
            3. 返回用户凭证信息

        """
        req = AuthorizeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        credential = self.oauth_service.oauth_login(provider_name, req.code.data)

        return success_json(AuthorizeResp().dump(credential))
