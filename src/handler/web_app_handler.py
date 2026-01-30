from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from flask import request
from flask_login import current_user, login_required
from injector import inject

from pkg.response import (
    compact_generate_response,
    success_json,
    validate_error_json,
)
from pkg.response.response import Response, success_message_json
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.web_app_schema import (
    GetConversationsReq,
    GetConversationsResp,
    WebAppChatReq,
)
from src.service import WebAppService


@inject
@dataclass
class WebAppHandler:
    """WebApp处理器"""

    web_app_service: WebAppService

    @route("/<string:token>", methods=["GET"])
    @swag_from(get_swagger_path("web_app_handler/get_web_app.yaml"))
    @login_required
    def get_web_app(self, token: str) -> Response:
        """根据传递的token凭证标识获取WebApp基础信息"""
        # 1.调用服务根据传递的token获取应用信息（添加features模型特性）
        resp = self.web_app_service.get_web_app_info(token)

        # 2.返回成功响应
        return success_json(resp)

    @route("/<string:token>/chat", methods=["POST"])
    @swag_from(get_swagger_path("web_app_handler/web_app_chat.yaml"))
    @login_required
    def web_app_chat(self, token: str) -> Response:
        """根据传递的token+query等信息与WebApp进行对话"""
        # 1.提取请求并校验
        req = WebAppChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.嗲用服务获取对应响应内容
        response = self.web_app_service.web_app_chat(token, req, current_user)

        return compact_generate_response(response)

    @route("/<string:token>/chat/<uuid:task_id>/stop", methods=["POST"])
    @swag_from(get_swagger_path("web_app_handler/stop_web_app_chat.yaml"))
    @login_required
    def stop_web_app_chat(self, token: str, task_id: UUID) -> Response:
        """根据传递的token+task_id停止与WebApp的对话"""
        self.web_app_service.stop_web_app_chat(token, task_id, current_user)
        return success_message_json("停止WebApp会话成功")

    @route("/<string:token>/conversations", methods=["GET"])
    @swag_from(get_swagger_path("web_app_handler/get_conversations.yaml"))
    @login_required
    def get_conversations(self, token: str) -> Response:
        """根据传递的token+is_pinned获取指定WebApp下的所有会话列表信息"""
        # 1.提取请求并校验
        req = GetConversationsReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取会话列表
        conversations = self.web_app_service.get_conversations(
            token=token,
            is_pinned=req.is_pinned.data,
            account=current_user,
        )

        # 3.构建响应并返回
        resp = GetConversationsResp(many=True)

        return success_json(resp.dump(conversations))
