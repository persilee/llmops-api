import os
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from internal.model import App
from internal.router import route
from internal.schema.app_schema import CompletionReq
from internal.service import AppService
from pkg.response import success_message_json, validate_error_json


@inject
@dataclass
class AppHandler:
    app_service: AppService

    @route("/create", methods=["POST"])
    def create_app(self):
        app = self.app_service.create_app()

        return success_message_json(f"创建成功，app id: {app.id}")

    @route("/<uuid:app_id>", methods=["GET"])
    def get_app(self, app_id: UUID):
        """获取 App 表"""
        app: App = self.app_service.get_app(app_id)

        return success_message_json(f"获取成功, app: {app.name}")

    @route("/<uuid:app_id>", methods=["POST"])
    def update_app(self, app_id: UUID):
        """更新 App 表"""
        app: App = self.app_service.update_app(app_id)

        return success_message_json(f"更新成功, app: {app.name}")

    @route("/<uuid:app_id>/delete", methods=["POST"])
    def delete_app(self, app_id: UUID):
        """删除 App 表"""
        app: App = self.app_service.delete_app(app_id)

        return success_message_json(f"删除成功, app: {app.name}")

    @route("/<uuid:app_id>/debug", methods=["POST"])
    def completion(self, app_id: UUID):
        """聊天机器人接口"""

        req = CompletionReq()

        if not req.validate():
            return validate_error_json(req.errors)

        # 导入必要的模板和模型组件
        prompt = ChatPromptTemplate.from_template("{query}")  # 创建一个基于模板的提示，使用query作为变量
        llm = ChatOpenAI(base_url=os.getenv("OPENAI_API_BASE_URL"),
                         model="gpt-3.5-turbo-16k")  # 初始化OpenAI的聊天模型，使用gpt-4-turbo版本
        parser = StrOutputParser()  # 创建一个字符串输出解析器

        # 将提示、语言模型和解析器连接成一个处理链
        chain = prompt | llm | parser

        # 使用用户查询调用处理链，获取处理后的内容
        content = chain.invoke({"query": req.query.data})

        # 返回包含处理内容的成功消息JSON
        return success_message_json(content)
