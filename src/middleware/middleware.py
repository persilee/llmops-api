from dataclasses import dataclass

from flask import Request
from injector import inject

from src.exception.exception import UnauthorizedException
from src.model.account import Account
from src.service.account_service import AccountService
from src.service.jwt_service import JwtService


@inject
@dataclass
class Middleware:
    jwt_service: JwtService
    account_service: AccountService

    def request_loader(self, request: Request) -> Account | None:
        if request.blueprint == "llmops":
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                error_msg = "该接口需要认证，请提供Authorization头"
                raise UnauthorizedException(error_msg)

            if " " not in auth_header:
                error_msg = "Authorization头格式错误，请提供Bearer token"
                raise UnauthorizedException(error_msg)

            auth_schema, access_token = auth_header.split(None, 1)
            if auth_schema.lower() != "bearer":
                error_msg = "Authorization头格式错误，请提供Bearer token"
                raise UnauthorizedException(error_msg)

            payload = self.jwt_service.decode_token(access_token)
            account_id = payload.get("sub")

            return self.account_service.get_account(account_id)
        return None
