from dataclasses import dataclass

from flasgger import swag_from
from flask import Response, request
from flask_login import current_user, login_required
from injector import inject

from pkg.response.response import (
    success_json,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.auth_schema import (
    LoginResp,
    PasswordLoginReq,
    PhoneNumberLoginReq,
    SendMailCodeReq,
    SendSMSCodeReq,
)
from src.service.account_service import AccountService
from src.service.mail_service import MailService
from src.service.sms_service import SmsService

# 手机号长度常量
PHONE_NUMBER_LENGTH = 11


@inject
@dataclass
class AuthHandler:
    account_service: AccountService
    sms_service: SmsService
    mail_service: MailService

    @route("/password-login", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/password_login.yaml"))
    def password_login(self) -> Response:
        """处理用户密码登录请求

        通过邮箱和密码进行用户认证，成功后返回登录凭证和会话ID

        Returns:
            Response: 包含登录凭证和会话ID的JSON响应

        """
        # 创建并验证登录请求
        req = PasswordLoginReq()
        if not req.validate():
            return validate_error_json(req.errors)

        account = req.account.data
        is_phone = account.isdigit() and len(account) == PHONE_NUMBER_LENGTH

        # 调用账户服务进行密码登录验证
        credential = self.account_service.password_login(
            account,
            req.password.data,
            is_phone=is_phone,
        )

        # 创建响应对象并返回登录凭证
        resp = LoginResp()

        return success_json(resp.dump(credential))

    @route("/phone-number-login", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/phone_number_login.yaml"))
    def phone_number_login(self) -> Response:
        req = PhoneNumberLoginReq()
        if not req.validate():
            return validate_error_json(req.errors)

        credential = self.account_service.phone_number_login(
            req.phone_number.data,
            req.code.data,
        )

        resp = LoginResp()

        return success_json(resp.dump(credential))

    @route("/send-sms-code", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/send_sms_code.yaml"))
    def send_sms_code(self) -> None:
        req = SendSMSCodeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.sms_service.send_sms_verify_code(req.phone_number.data)

        return success_message_json("短信验证码发送成功")

    @route("/send-mail-code", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/send_mail_code.yaml"))
    def send_mail_code(self) -> None:
        req = SendMailCodeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.mail_service.send_mail_verify_code(req.email.data)

        return success_message_json("邮箱验证码发送成功")

    @route("/logout", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/logout.yaml"))
    @login_required
    def logout(self) -> Response:
        """处理用户登出请求

        通过调用Flask-Login的logout_user()函数来清除用户的会话信息，
        同时从Redis中删除对应的会话数据，完成用户登出操作。
        需要用户已登录才能访问此接口。

        Returns:
            Response: 包含登出成功消息的JSON响应

        """
        # 获取会话ID（从请求头或请求体中）
        session_id = request.headers.get("X-Session-ID")
        if not session_id and request.is_json:
            session_id = request.json.get("session_id")

        self.account_service.logout(session_id)

        # 返回登出成功的消息响应
        return success_message_json("退出登录成功")

    @route("/logout-all", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/logout_all.yaml"))
    @login_required
    def logout_all(self) -> Response:
        """处理用户所有设备登出请求

        清除用户在所有设备上的会话信息，从Redis中删除该用户的所有会话数据。
        需要用户已登录才能访问此接口。

        Returns:
            Response: 包含登出成功消息的JSON响应

        """
        self.account_service.logout_all(str(current_user.id))

        # 返回登出成功的消息响应
        return success_message_json("已退出所有设备的登录")
