from dataclasses import dataclass

from flasgger import swag_from
from flask_login import current_user, login_required
from injector import inject

from pkg.response.response import Response, success_json, validate_error_json
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.builtin_app_schema import (
    AddBuiltinAppToSpaceReq,
    GetBuiltinAppCategoriesResp,
    GetBuiltinAppsResp,
)
from src.service.builtin_app_service import BuiltinAppService


@inject
@dataclass
class BuiltinAppHandler:
    """内置应用处理器类

    该类负责处理所有与内置应用相关的HTTP请求，包括：
    - 获取内置应用分类列表
    - 获取内置应用列表
    - 将内置应用复制到用户空间

    Attributes:
        builtin_app_service (BuiltinAppService): 内置应用服务类实例，
        用于处理具体的业务逻辑

    """

    builtin_app_service: BuiltinAppService

    @route("/categories", methods=["GET"])
    @swag_from(get_swagger_path("builtin_app_handler/get_builtin_app_categories.yaml"))
    @login_required
    def get_builtin_app_categories(self) -> Response:
        """获取内置应用分类列表

        该接口用于获取系统中所有内置应用的分类信息。需要用户登录后才能访问。

        Returns:
            Response: 包含分类列表的响应对象，每个分类包含分类ID和名称等信息

        """
        categories = self.builtin_app_service.get_categories()

        resp = GetBuiltinAppCategoriesResp(many=True)

        return success_json(resp.dump(categories))

    @route("/apps", methods=["GET"])
    @swag_from(get_swagger_path("builtin_app_handler/get_builtin_apps.yaml"))
    @login_required
    def get_builtin_apps(self) -> Response:
        """获取内置应用列表

        该接口用于获取系统中所有可用的内置应用信息。需要用户登录后才能访问。

        Returns:
            Response: 包含应用列表的响应对象，每个应用包含ID、名称、描述等详细信息

        """
        builtin_apps = self.builtin_app_service.get_builtin_apps()

        resp = GetBuiltinAppsResp(many=True)

        return success_json(resp.dump(builtin_apps))

    @route("/copy-to-space", methods=["POST"])
    @swag_from(get_swagger_path("builtin_app_handler/add_builtin_app_to_space.yaml"))
    @login_required
    def add_builtin_app_to_space(self) -> Response:
        """将内置应用复制到用户空间

        该接口用于将选定的内置应用复制到当前用户的空间中。需要用户登录后才能访问。
        请求体中需要包含要复制的内置应用ID。

        Returns:
            Response: 包含复制后应用ID的响应对象
                - app_id: 新创建的应用ID

        Raises:
            ValidationError: 当请求数据验证失败时
            UnauthorizedError: 当用户未登录时
            NotFoundError: 当指定的内置应用不存在时

        """
        req = AddBuiltinAppToSpaceReq()
        if not req.validate():
            return validate_error_json(req.errors)

        app = self.builtin_app_service.add_builtin_app_to_space(
            req.builtin_app_id.data,
            current_user,
        )

        return success_json({"app_id": app.id})
