import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from flasgger import swag_from
from injector import inject
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

from pkg.response import success_message_json, validate_error_json
from pkg.response.response import fail_message_json, success_json
from src.model import App
from src.router import route
from src.schemas.app_schema import CompletionReq
from src.service import AppService

if TYPE_CHECKING:
    from src.model import App


@inject
@dataclass
class AppHandler:
    app_service: AppService

    @route("/create", methods=["POST"])
    @swag_from("../../docs/app_handler/create_app.yaml")
    def create_app(self) -> str:
        app = self.app_service.create_app()

        return success_message_json(f"创建成功，app_id: {app.id}")

    @route("/<uuid:app_id>", methods=["GET"])
    @swag_from("../../docs/app_handler/get_app.yaml")
    def get_app(self, app_id: UUID) -> str:
        app: App = self.app_service.get_app(app_id)

        return success_message_json(f"获取成功, app_id: {app.id}")

    @route("/<uuid:app_id>", methods=["POST"])
    @swag_from("../../docs/app_handler/update_app.yaml")
    def update_app(self, app_id: UUID) -> str:
        """更新 App 表"""
        app: App = self.app_service.update_app(app_id)

        return success_message_json(f"更新成功, app_id: {app.id}")

    @route("/<uuid:app_id>/delete", methods=["POST"])
    @swag_from("../../docs/app_handler/delete_app.yaml")
    def delete_app(self, app_id: UUID) -> str:
        app: App = self.app_service.get_app(app_id)
        if app is not None:
            """删除 App 表"""
            app: App = self.app_service.delete_app(app_id)

            return success_message_json(f"删除成功, app_id: {app.id}")
        return fail_message_json(f"删除失败,记录不存在，app_id: {app_id}")

    @route("/<uuid:app_id>/debug", methods=["POST"])
    @swag_from("../../docs/app_handler/debug.yaml")
    def completion(self, app_id: UUID) -> str:
        """聊天机器人接口"""
        req = CompletionReq()

        if not req.validate():
            return validate_error_json(req.errors)

        prompt = ChatPromptTemplate(
            [
                ("system", "你是一个聊天机器人，请根据用户输入回答问题"),
                MessagesPlaceholder("history"),
                ("human", "{query}"),
            ],
        )

        memory_dir = Path("./storage/memory")
        memory_dir.mkdir(parents=True, exist_ok=True)
        chat_memory = FileChatMessageHistory("./storage/memory/chat_history.json")

        memory = ConversationBufferWindowMemory(
            k=3,
            return_messages=True,
            chat_memory=chat_memory,
        )

        llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL"),
            model="gpt-3.5-turbo-16k",
        )

        chain = (
            RunnablePassthrough.assign(
                history=RunnableLambda(
                    lambda x: memory.load_memory_variables(x)["history"],
                ),
            )
            | prompt
            | llm
            | StrOutputParser()
        )

        chat_input = {"query": req.query.data}
        content = chain.invoke(chat_input)
        memory.save_context(chat_input, {"output": content})

        # 返回包含处理内容的成功消息JSON
        return success_json({"content": content})
