from dataclasses import dataclass

from flasgger import swag_from
from flask_login import current_user, login_required
from injector import inject

from pkg.response.response import (
    Response,
    success_json,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.account_schema import (
    GetCurrentUserResp,
    UpdateAvatarReq,
    UpdateNameReq,
    UpdatePasswordReq,
)
from src.service.account_service import AccountService


@inject
@dataclass
class AccountHandler:
    account_service: AccountService

    @route("/", methods=["GET"])
    @swag_from(get_swagger_path("account_handler/get_current_user.yaml"))
    @login_required
    def get_current_user(self) -> Response:
        """获取当前用户信息

        Returns:
            Response: 包含当前用户信息的响应对象

        """
        resp = GetCurrentUserResp()

        return success_json(resp.dump(current_user))

    @route("/update-password", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/update_password.yaml"))
    @login_required
    def update_password(self) -> Response:
        """更新用户密码

        Returns:
            Response: 操作结果响应对象

        """
        req = UpdatePasswordReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.update_password(req.password.data, current_user)

        return success_message_json("修改密码成功")

    @route("/update-name", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/update_name.yaml"))
    @login_required
    def update_name(self) -> Response:
        """更新用户昵称

        Returns:
            Response: 操作结果响应对象

        """
        req = UpdateNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.update_account(current_user, name=req.name.data)

        return success_message_json("修改昵称成功")

    @route("/update-avatar", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/update_avatar.yaml"))
    @login_required
    def update_avatar(self) -> Response:
        """更新用户头像

        Returns:
            Response: 操作结果响应对象

        """
        req = UpdateAvatarReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.update_account(current_user, avatar=req.avatar.data)

        return success_message_json("修改头像成功")
