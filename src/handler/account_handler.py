from dataclasses import dataclass

from flasgger import swag_from
from flask import request
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
    BindEmailReq,
    BindPhoneNumberReq,
    GetCurrentUserResp,
    UpdateAvatarReq,
    UpdateNameReq,
    UpdatePasswordReq,
)
from src.schemas.auth_schema import (
    GetPointsByDateRangeReq,
    SendMailCodeReq,
    SendSMSCodeReq,
    UnbindOAuthProviderReq,
)
from src.service.account_service import AccountService
from src.service.points_service import PointsService


@inject
@dataclass
class AccountHandler:
    account_service: AccountService
    points_service: PointsService

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

    @route("/bind-phone-number", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/bind_phone_number.yaml"))
    @login_required
    def bind_phone_number(self) -> Response:
        req = BindPhoneNumberReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.bind_phone_number(
            req.phone_number.data,
            req.code.data,
            current_user,
        )

        return success_message_json("绑定手机号成功")

    @route("/bind-email", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/bind_email.yaml"))
    @login_required
    def bind_email(self) -> Response:
        req = BindEmailReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.bind_email(
            req.email.data,
            req.code.data,
            current_user,
        )

        return success_message_json("绑定邮箱成功")

    @route("/is-phone-number-bound", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/is_phone_number_bound.yaml"))
    @login_required
    def is_phone_number_bound(self) -> Response:
        req = SendSMSCodeReq()

        if not req.validate():
            return validate_error_json(req.errors)

        result = self.account_service.is_phone_number_bound(req.phone_number.data)

        return success_json({"is_bound": result})

    @route("/is-email-bound", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/is_email_bound.yaml"))
    @login_required
    def is_email_bound(self) -> Response:
        req = SendMailCodeReq()

        if not req.validate():
            return validate_error_json(req.errors)

        result = self.account_service.is_email_bound(req.email.data)

        return success_json({"is_bound": result})

    @route("/unbind-oauth-provider", methods=["POST"])
    @swag_from(get_swagger_path("account_handler/unbind_oauth_provider.yaml"))
    @login_required
    def unbind_oauth_provider(self) -> Response:
        req = UnbindOAuthProviderReq()

        if not req.validate():
            return validate_error_json(req.errors)

        self.account_service.unbind_oauth_provider(req.provider_name.data, current_user)

        return success_message_json("解绑成功")

    @route("/points", methods=["GET"])
    @swag_from(get_swagger_path("account_handler/get_points_by_account_id.yaml"))
    @login_required
    def get_points_by_account_id(self) -> Response:
        points = self.points_service.get_points_by_account_id(current_user)

        return success_json({"points": points.available_points})

    @route("/get-deduct-points-by-date-range", methods=["GET"])
    @swag_from(get_swagger_path("account_handler/get_points_by_date_range.yaml"))
    @login_required
    def get_points_by_date_range(self) -> Response:
        req = GetPointsByDateRangeReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        points = self.points_service.get_points_by_date_range(
            start_date=req.start_date.data,
            end_date=req.end_date.data,
            account=current_user,
            include_details=req.include_details.data,
        )

        return success_json(points)
