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
    PasswordBindAccountReq,
    PasswordLoginReq,
    PhoneNumberBindAccountReq,
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

    @route("/password-bind-account", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/password_bind_account.yaml"))
    def password_bind_account(self) -> Response:
        """处理密码绑定账户请求

        该方法用于将OAuth账户与密码账户进行绑定，支持手机号和邮箱两种账户类型。

        Returns:
            Response: 包含登录凭证的JSON响应，成功时返回200状态码

        Raises:
            ValidationError: 当请求数据格式不正确时

        请求流程:
            1. 验证请求数据格式
            2. 判断账户类型（手机号或邮箱）
            3. 调用账户服务进行绑定操作
            4. 返回登录凭证

        """
        # 创建密码绑定账户请求对象
        req = PasswordBindAccountReq()
        # 验证请求数据格式是否正确
        if not req.validate():
            return validate_error_json(req.errors)

        # 获取账户信息
        account = req.account.data
        # 判断账户是否为手机号（纯数字且长度为11位）
        is_phone = account.isdigit() and len(account) == PHONE_NUMBER_LENGTH

        # 调用账户服务进行密码绑定账户操作
        credential = self.account_service.password_bind_account(
            account,  # 账户信息（手机号或邮箱）
            req.password.data,  # 密码
            req.oauth_info.data,  # OAuth信息
            is_phone=is_phone,  # 是否为手机号账户
        )

        # 创建登录响应对象
        resp = LoginResp()
        # 返回包含登录凭证的成功响应
        return success_json(resp.dump(credential))

    @route("/phone-number-login", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/phone_number_login.yaml"))
    def phone_number_login(self) -> Response:
        """手机号登录接口

        通过手机号和验证码进行登录验证。验证成功后返回登录凭证。

        Returns:
            Response: 包含登录凭证的JSON响应
                - 成功时返回包含登录凭证的响应
                - 验证失败时返回错误信息

        请求参数:
            phone_number: 手机号
            code: 验证码

        """
        # 创建手机号登录请求对象
        req = PhoneNumberLoginReq()
        # 验证请求数据格式是否正确
        if not req.validate():
            # 如果验证失败，返回错误信息
            return validate_error_json(req.errors)

        # 调用账户服务进行手机号登录验证
        credential = self.account_service.phone_number_login(
            req.phone_number.data,  # 手机号
            req.code.data,  # 验证码
        )

        # 创建登录响应对象
        resp = LoginResp()

        # 返回包含登录凭证的成功响应
        return success_json(resp.dump(credential))

    @route("/phone-number-bind-account", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/phone_number_bind_account.yaml"))
    def phone_number_bind_account(self) -> Response:
        """手机号绑定账号处理函数

        通过手机号和验证码绑定第三方账号

        Returns:
            Response: 包含登录凭证的JSON响应

        """
        # 创建并验证绑定请求
        req = PhoneNumberBindAccountReq()

        # 验证请求数据格式是否正确
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用账户服务进行手机号绑定
        credential = self.account_service.phone_number_bind_account(
            req.phone_number.data,  # 手机号
            req.code.data,  # 验证码
            req.oauth_info.data,  # 第三方登录信息
        )

        # 创建登录响应对象
        resp = LoginResp()

        # 返回包含登录凭证的成功响应
        return success_json(resp.dump(credential))

    @route("/send-sms-code", methods=["POST"])
    @swag_from(get_swagger_path("oauth_handler/send_sms_code.yaml"))
    def send_sms_code(self) -> None:
        """发送短信验证码

        通过手机号发送短信验证码，用于后续的手机号登录或绑定操作

        Returns:
            Response: 返回发送结果的JSON响应

        """
        req = SendSMSCodeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用短信服务发送验证码
        self.sms_service.send_sms_verify_code(req.phone_number.data)

        # 返回发送成功的响应
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
