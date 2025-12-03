import json
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from flasgger import swag_from
from flask_login import login_required
from injector import inject
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.runnables import (
    RunnableConfig,
)
from langchain_openai import ChatOpenAI
from redis import Redis

from pkg.response import success_message_json, validate_error_json
from pkg.response.response import (
    Response,
    compact_generate_response,
    fail_message_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.core.agent.agents.agent_queue_manager import AgentQueueManager
from src.core.agent.agents.function_call_agent import FunctionCallAgent
from src.core.agent.entities.agent_entity import AgentConfig
from src.core.tools.builtin_tools.providers import BuiltinProviderManager
from src.entity.conversation_entity import InvokeFrom
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
    redis_client: Redis

    @route("/create", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/create_app.yaml"))
    @login_required
    def create_app(self) -> str:
        app = self.app_service.create_app()

        return success_message_json(f"创建成功，app_id: {app.id}")

    @route("/<uuid:app_id>", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_app.yaml"))
    @login_required
    def get_app(self, app_id: UUID) -> str:
        app: App = self.app_service.get_app(app_id)

        return success_message_json(f"获取成功, app_id: {app.id}")

    @route("/<uuid:app_id>", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/update_app.yaml"))
    @login_required
    def update_app(self, app_id: UUID) -> str:
        """更新 App 表"""
        app: App = self.app_service.update_app(app_id)

        return success_message_json(f"更新成功, app_id: {app.id}")

    @route("/<uuid:app_id>/delete", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/delete_app.yaml"))
    @login_required
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
    @login_required
    def debug(self, app_id: UUID) -> Response:
        req = CompletionReq()
        if not req.validate():
            return validate_error_json(req.errors)

        tools = [
            self.builtin_provider_manager.get_tool("google", "google_serper")(),
            self.builtin_provider_manager.get_tool("gaode", "gaode_weather")(),
            self.builtin_provider_manager.get_tool("dalle", "dalle3")(),
        ]

        user_id = uuid.uuid4()

        agent = FunctionCallAgent(
            AgentConfig(
                user_id=user_id,
                llm=ChatOpenAI(model="gpt-4o-mini"),
                enable_long_term_memory=True,
                tools=tools,
            ),
            AgentQueueManager(
                user_id=user_id,
                task_id=uuid.uuid4(),
                invoke_from=InvokeFrom.DEBUGGER,
                redis_client=self.redis_client,
            ),
        )

        def stream_event_response() -> Generator:
            for agent_queue_event in agent.run(req.query.data, [], ""):
                data = {
                    "id": str(agent_queue_event.id),
                    "task_id": str(agent_queue_event.task_id),
                    "event": agent_queue_event.event,
                    "thought": agent_queue_event.thought,
                    "observation": agent_queue_event.observation,
                    "tool": agent_queue_event.tool,
                    "tool_input": agent_queue_event.tool_input,
                    "answer": agent_queue_event.answer,
                    "latency": agent_queue_event.latency,
                }
                yield f"event: {agent_queue_event.event}\ndata: {json.dumps(data)}\n\n"

        return compact_generate_response(stream_event_response())

    @route("/ping", methods=["GET"])
    def ping(self) -> Response:
        test_task.delay(uuid.uuid4())
        return "pong"
