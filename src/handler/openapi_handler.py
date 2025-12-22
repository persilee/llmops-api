from dataclasses import dataclass

from flasgger import swag_from
from flask_login import login_required
from injector import inject

from pkg.response.response import Response, success_message_json
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route


@inject
@dataclass
class OpenApiHandler:
    @route("/chat", methods=["GET"])
    @swag_from(
        get_swagger_path("api_key_handler/chat.yaml"),
    )
    @login_required
    def chat(self) -> Response:
        return success_message_json()
