import json
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from flasgger import swag_from
from injector import inject
from langchain.messages import ToolMessage
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import (
    RunnableConfig,
    RunnableLambda,
    RunnablePassthrough,
)
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langgraph.graph import END, MessagesState, StateGraph

from pkg.response import success_message_json, validate_error_json
from pkg.response.response import (
    Response,
    compact_generate_response,
    fail_message_json,
    success_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.core.tools.builtin_tools.providers import BuiltinProviderManager
from src.model import App
from src.router import route
from src.schemas.app_schema import CompletionReq
from src.service import AppService, VectorDatabaseService
from src.service.api_tool_service import ApiToolService
from src.task import test_task

if TYPE_CHECKING:
    from src.model import App


@inject
@dataclass
class AppHandler:
    app_service: AppService
    vector_database_service: VectorDatabaseService
    api_tool_service: ApiToolService
    builtin_provider_manager: BuiltinProviderManager

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
        _inputs: dict[str, Any],
        config: RunnableConfig,
    ) -> dict[str, Any]:
        configurable = config.get("configurable", {})
        session_id = configurable.get("session_id", "")

        if session_id:
            # 获取对应会话的历史记录
            history_file = f"./storage/memory/chat_history_{session_id}.json"
            try:
                chat_history = FileChatMessageHistory(history_file)
                messages = chat_history.messages
            except (FileNotFoundError, OSError, ValueError):
                messages = []

        return {"history": messages}

    @route("/<uuid:app_id>/debug", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/debug.yaml"))
    def debug(self, app_id: UUID) -> Response:  # noqa: PLR0915
        req = CompletionReq()
        if not req.validate():
            return validate_error_json(req.errors)

        q = Queue()
        query = req.query.data

        def graph_app() -> None:
            tools = [
                self.builtin_provider_manager.get_tool("google", "google_serper")(),
                self.builtin_provider_manager.get_tool("gaode", "gaode_weather")(),
                self.builtin_provider_manager.get_tool("dalle", "dalle3")(),
            ]

            def chatbot(state: MessagesState) -> MessagesState:
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7).bind_tools(tools)

                is_first_chunk = True
                is_tool_call = False
                gathered = None
                id = str(uuid.uuid4())
                for chunk in llm.stream(state["messages"]):
                    if is_first_chunk and chunk.content == "" and not chunk.tool_calls:
                        continue
                    if is_first_chunk:
                        gathered = chunk
                        is_first_chunk = False
                    else:
                        gathered += chunk
                    if chunk.tool_calls or is_tool_call:
                        is_tool_call = True
                        q.put(
                            {
                                "id": id,
                                "event": "agent_thought",
                                "data": json.dumps(chunk.tool_call_chunks),
                            },
                        )
                    else:
                        q.put(
                            {
                                "id": id,
                                "event": "agent_message",
                                "data": chunk.content,
                            },
                        )
                return {"messages": [gathered]}

            def tool_executor(state: MessagesState) -> MessagesState:
                tool_calls = state["messages"][-1].tool_calls

                tools_by_name = {tool.name: tool for tool in tools}

                messages = []
                for tool_call in tool_calls:
                    id = str(uuid.uuid4())
                    tool = tools_by_name[tool_call["name"]]
                    tool_result = tool.invoke(tool_call["args"])
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"],
                            content=json.dumps(tool_result),
                            name=tool_call["name"],
                        ),
                    )
                    q.put(
                        {
                            "id": id,
                            "event": "agent_action",
                            "data": json.dumps(tool_result),
                        },
                    )

                return {"messages": messages}

            def route(state: MessagesState) -> Literal["tool_executor", "__end__"]:
                ai_message = state["messages"][-1]
                if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
                    return "tool_executor"
                return END

            graph_builder = StateGraph(MessagesState)

            graph_builder.add_node("llm", chatbot)
            graph_builder.add_node("tool_executor", tool_executor)

            graph_builder.set_entry_point("llm")
            graph_builder.add_conditional_edges("llm", route)
            graph_builder.add_edge("tool_executor", "llm")

            graph = graph_builder.compile()

            result = graph.invoke({"messages": [("human", query)]})
            print("result", result)
            q.put(None)

        def stream_event_response() -> Generator:
            while True:
                item = q.get()
                if item is None:
                    break
                yield f"event: {item.get('event')}\ndata: {json.dumps(item)}\n\n"
                q.task_done()

        t = Thread(target=graph_app)
        t.start()

        return compact_generate_response(stream_event_response())

    def _debug(self, app_id: UUID) -> str:
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

        def get_session_history(session_id: str) -> BaseChatMessageHistory:
            return chat_memory

        llm = ChatOpenAI(
            model="gpt-3.5-turbo-16k",
        )

        chain = (
            RunnablePassthrough.assign(
                history=RunnableLambda(
                    lambda x: self._load_memory_variables(
                        x,
                        RunnableConfig(configurable={"session_id": str(app_id)}),
                    ),
                )
                | itemgetter("history"),
                context=itemgetter("query")
                | self.vector_database_service.get_retriever()
                | self.vector_database_service.combine_documents,
            )
            | prompt
            | llm
            | StrOutputParser()
        )

        runnable_with_history = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="query",
            history_messages_key="history",
        )

        chat_input = {"query": req.query.data}
        content = runnable_with_history.invoke(
            chat_input,
            config={"configurable": {"session_id": str(app_id)}},
        )

        # 返回包含处理内容的成功消息JSON
        return success_json({"content": content})

    @route("/ping", methods=["GET"])
    def ping(self) -> Response:
        test_task.delay(uuid.uuid4())
        return "pong"
