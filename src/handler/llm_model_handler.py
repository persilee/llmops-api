import io
from dataclasses import dataclass

from flasgger import swag_from
from flask import send_file
from flask_login import login_required
from injector import inject

from pkg.response import success_json
from pkg.response.response import Response
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.service import LLMModelService


@inject
@dataclass
class LLMModelHandler:
    """语言模型处理器"""

    llm_model_service: LLMModelService

    @route("", methods=["GET"])
    @swag_from(get_swagger_path("llm_model_handler/get_llm_models.yaml"))
    @login_required
    def get_llm_models(self) -> Response:
        """获取所有的语言模型提供商信息"""
        return success_json(self.llm_model_service.get_language_models())

    @route("/<string:provider_name>/<string:model_name>", methods=["GET"])
    @swag_from(get_swagger_path("llm_model_handler/get_llm_model.yaml"))
    @login_required
    def get_llm_model(self, provider_name: str, model_name: str) -> Response:
        """根据传递的提供商名字+模型名字获取模型详细信息"""
        return success_json(
            self.llm_model_service.get_language_model(provider_name, model_name),
        )

    @route("/<string:provider_name>/icon", methods=["GET"])
    @swag_from(get_swagger_path("llm_model_handler/get_llm_model_icon.yaml"))
    def get_llm_model_icon(self, provider_name: str) -> Response:
        """根据传递的提供者名字获取指定提供商的icon图标"""
        icon, mimetype = self.llm_model_service.get_language_model_icon(
            provider_name,
        )
        return send_file(io.BytesIO(icon), mimetype)
