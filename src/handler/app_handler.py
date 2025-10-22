from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from flasgger import swag_from
from injector import inject
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.memory import BaseMemory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import (
    RunnableConfig,
    RunnableLambda,
    RunnablePassthrough,
)
from langchain_core.tracers import Run
from langchain_openai import ChatOpenAI

from pkg.response import success_message_json, validate_error_json
from pkg.response.response import Response, fail_message_json, success_json
from pkg.swagger.swagger import get_swagger_path
from src.model import App
from src.router import route
from src.schemas.app_schema import CompletionReq
from src.service import AppService, VectorDatabaseService

if TYPE_CHECKING:
    from src.model import App


@inject
@dataclass
class AppHandler:
    app_service: AppService
    vector_database_service: VectorDatabaseService

    @route("/create", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/create_app.yaml"))
    def create_app(self) -> str:
        app = self.app_service.create_app()

        return success_message_json(f"创建成功，app_id: {app.id}")

    @route("/<uuid:app_id>", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_app.yaml"))
    def get_app(self, app_id: UUID) -> str:
        app: App = self.app_service.get_app(app_id)

        return success_message_json(f"获取成功, app_id: {app.id}")

    @route("/<uuid:app_id>", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/update_app.yaml"))
    def update_app(self, app_id: UUID) -> str:
        """更新 App 表"""
        app: App = self.app_service.update_app(app_id)

        return success_message_json(f"更新成功, app_id: {app.id}")

    @route("/<uuid:app_id>/delete", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/delete_app.yaml"))
    def delete_app(self, app_id: UUID) -> str:
        app: App = self.app_service.get_app(app_id)
        if app is not None:
            """删除 App 表"""
            app: App = self.app_service.delete_app(app_id)

            return success_message_json(f"删除成功, app_id: {app.id}")
        return fail_message_json(f"删除失败,记录不存在，app_id: {app_id}")

    @classmethod
    def _load_memory_variables(
        cls,
        inputs: dict[str, Any],
        config: RunnableConfig,
    ) -> dict[str, Any]:
        configurable = config.get("configurable", {})
        configurable_memory = configurable.get("memory", None)
        if configurable_memory is not None and isinstance(
            configurable_memory,
            BaseMemory,
        ):
            return configurable_memory.load_memory_variables(inputs)
        return {"history", []}

    @classmethod
    def _save_context(cls, run_obj: Run, config: RunnableConfig) -> None:
        configurable = config.get("configurable", {})
        configurable_memory = configurable.get("memory", None)
        if configurable_memory is not None and isinstance(
            configurable_memory,
            BaseMemory,
        ):
            configurable_memory.save_context(run_obj.inputs, run_obj.outputs)

    @route("/<uuid:app_id>/debug", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/debug.yaml"))
    def debug(self, app_id: UUID) -> str:
        """聊天机器人接口"""
        req = CompletionReq()

        if not req.validate():
            return validate_error_json(req.errors)

        system_prompt = (
            "你是一个聊天机器人，能根据对应的上下文和历史对话信息回复用户信息。\n\n"
            "<context>{context}</context>"
        )

        prompt = ChatPromptTemplate(
            [
                ("system", system_prompt),
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
            model="gpt-3.5-turbo-16k",
        )

        chain = (
            RunnablePassthrough.assign(
                history=RunnableLambda(
                    self._load_memory_variables,
                )
                | itemgetter("history"),
                context=itemgetter("query")
                | self.vector_database_service.get_retriever()
                | self.vector_database_service.combine_documents,
            )
            | prompt
            | llm
            | StrOutputParser()
        ).with_listeners(on_end=self._save_context)

        chat_input = {"query": req.query.data}
        content = chain.invoke(chat_input, config={"configurable": {"memory": memory}})

        # 返回包含处理内容的成功消息JSON
        return success_json({"content": content})

    @route("/ping", methods=["GET"])
    def ping(self) -> Response:
        return success_json({"content": "pong"})
