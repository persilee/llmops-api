import os
import uuid
from dataclasses import dataclass

from flask import request
from injector import inject
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam

from internal.model import App
from internal.schema.app_schema import CompletionReq
from internal.service import AppService
from pkg.response import success_json, validate_error_json, success_message_json


@inject
@dataclass
class AppHandler:
    """
    AppHandler 是一个处理聊天机器人相关请求的处理器类。

    核心功能：
    - 提供聊天机器人接口，处理用户查询并返回 AI 助手的回复

    代码示例：
        ```python
        response = AppHandler.completion()
        print(response)  # 打印 AI 助手的回复
        ```

    使用限制：
    - 需要正确配置环境变量 OPENAI_API_BASE_URL
    - 请求必须包含有效的 query 参数
    """

    app_service: AppService

    def create_app(self):
        """创建 App 表"""
        app = self.app_service.create_app()

        return success_message_json(f"创建成功, app: {app}")

    def get_app(self, app_id: uuid.UUID):
        """获取 App 表"""
        app: App = self.app_service.get_app(app_id)

        return success_message_json(f"获取成功, app: {app.name}")

    def update_app(self, app_id: uuid.UUID):
        """更新 App 表"""
        app: App = self.app_service.update_app(app_id)

        return success_message_json(f"更新成功, app: {app.name}")

    def delete_app(self, app_id: uuid.UUID):
        """删除 App 表"""
        app: App = self.app_service.delete_app(app_id)

        return success_message_json(f"删除成功, app: {app.name}")

    @staticmethod
    def completion():
        """聊天机器人接口"""

        req = CompletionReq()

        if not req.validate():
            return validate_error_json(req.errors)

        query = request.json.get("query")
        client = OpenAI(base_url=os.getenv("OPENAI_API_BASE_URL"))
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                ChatCompletionUserMessageParam(role="user", content=query)
            ]
        )

        content = completion.choices[0].message.content

        return success_json({"content": content})
