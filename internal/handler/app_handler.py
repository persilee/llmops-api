import os
import uuid
from dataclasses import dataclass

from flask import request
from injector import inject
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam

from internal.model import App
from internal.router import route
from internal.schema.app_schema import CompletionReq
from internal.service import AppService
from pkg.response import success_message_json, validate_error_json, success_json


@inject
@dataclass
class AppHandler:
    app_service: AppService

    @route("/create", methods=["POST"])
    def create_app(self):
        app = self.app_service.create_app()

        return success_message_json(f"创建成功，app id: {app.id}")

    @route("/<uuid:app_id>", methods=["GET"])
    def get_app(self, app_id: uuid.UUID):
        """获取 App 表"""
        app: App = self.app_service.get_app(app_id)

        return success_message_json(f"获取成功, app: {app.name}")

    @route("/<uuid:app_id>", methods=["POST"])
    def update_app(self, app_id: uuid.UUID):
        """更新 App 表"""
        app: App = self.app_service.update_app(app_id)

        return success_message_json(f"更新成功, app: {app.name}")

    @route("/<uuid:app_id>/delete", methods=["POST"])
    def delete_app(self, app_id: uuid.UUID):
        """删除 App 表"""
        app: App = self.app_service.delete_app(app_id)

        return success_message_json(f"删除成功, app: {app.name}")

    @staticmethod
    @route("/completion", methods=["POST"])
    def completion():
        """聊天机器人接口"""

        req = CompletionReq()

        if not req.validate():
            return validate_error_json(req.errors)

        query = request.json.get("query")
        client = OpenAI(base_url=os.getenv("OPENAI_API_BASE_URL"))
        result = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                ChatCompletionUserMessageParam(role="user", content=query)
            ]
        )

        content = result.choices[0].message.content

        return success_json({"content": content})
