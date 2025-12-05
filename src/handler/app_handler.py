from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from flasgger import swag_from
from flask_login import current_user, login_required
from injector import inject

from pkg.response import success_message_json
from pkg.response.response import (
    Response,
    fail_message_json,
    success_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.model import App
from src.router import route
from src.schemas.app_schema import CreateAppReq, GetAppResp
from src.service import AppService

if TYPE_CHECKING:
    from src.model import App


@inject
@dataclass
class AppHandler:
    app_service: AppService

    @route("/create", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/create_app.yaml"))
    @login_required
    def create_app(self) -> str:
        """创建新的应用

        通过POST请求创建一个新的应用实例。需要用户登录后才能访问。
        请求体需要包含创建应用所需的信息，通过CreateAppReq进行验证。

        Returns:
            str: JSON格式的响应字符串，包含新创建应用的ID

        """
        req = CreateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        app = self.app_service.create_app(req, current_user)

        return success_json({"id": app.id})

    @route("/<uuid:app_id>", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_app.yaml"))
    @login_required
    def get_app(self, app_id: UUID) -> str:
        """获取指定应用的信息

        通过GET请求获取指定ID的应用详细信息。需要用户登录后才能访问。
        返回的信息经过GetAppResp模式化处理。

        Args:
            app_id (UUID): 要查询的应用的唯一标识符

        Returns:
            str: JSON格式的响应字符串，包含应用的详细信息

        """
        app: App = self.app_service.get_app(app_id, current_user)

        resp = GetAppResp()

        return success_json(resp.dump(app))

    @route("/<uuid:app_id>", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/update_app.yaml"))
    @login_required
    def update_app(self, app_id: UUID) -> str:
        """更新 App 表"""
        app: App = self.app_service.update_app(app_id)

        return success_message_json(f"更新成功, app_id: {app.id}")

    @route("/<uuid:app_id>/delete", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/delete_app.yaml"))
    @login_required
    def delete_app(self, app_id: UUID) -> str:
        app: App = self.app_service.get_app(app_id)
        if app is not None:
            """删除 App 表"""
            app: App = self.app_service.delete_app(app_id)

            return success_message_json(f"删除成功, app_id: {app.id}")
        return fail_message_json(f"删除失败,记录不存在，app_id: {app_id}")

    @route("/ping", methods=["GET"])
    def ping(self) -> Response:
        return "pong"
