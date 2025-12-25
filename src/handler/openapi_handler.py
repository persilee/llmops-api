from dataclasses import dataclass

from flasgger import swag_from
from flask_login import current_user, login_required
from injector import inject

from pkg.response.response import (
    Response,
    compact_generate_response,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.openapi_schema import OpenAPIChatReq
from src.service.openapi_service import OpenAPIService


@inject
@dataclass
class OpenApiHandler:
    openapi_service: OpenAPIService

    @route("/chat", methods=["POST"])
    @swag_from(
        get_swagger_path("api_key_handler/chat.yaml"),
    )
    @login_required
    def chat(self) -> Response:
        req = OpenAPIChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        resp = self.openapi_service.chat(req, current_user)

        return compact_generate_response(resp)
