from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from flasgger import swag_from
from flask import request
from flask_login import current_user, login_required
from injector import inject

from pkg.paginator.paginator import PageModel
from pkg.response import success_message_json
from pkg.response.response import (
    Response,
    compact_generate_response,
    not_found_message_json,
    success_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.core.llm_model.llm_model_manager import LLMModelManager
from src.model import App
from src.router import route
from src.schemas.app_schema import (
    CreateAppReq,
    DebugChatReq,
    FallbackHistoryToDraftReq,
    GenerateShareConversationReq,
    GetAppResp,
    GetAppsWithPageReq,
    GetAppsWithPageResp,
    GetDebugConversationMessagesWithPageReq,
    GetDebugConversationMessagesWithPageResp,
    GetPublishHistoriesWithPageReq,
    GetPublishHistoriesWithPageResp,
    UpdateAppReq,
    UpdateDebugConversationSummaryReq,
)
from src.service import AppService
from src.service.conversation_service import ConversationService

if TYPE_CHECKING:
    from src.model import App


@inject
@dataclass
class AppHandler:
    app_service: AppService
    llm_model_manager: LLMModelManager
    conversation_service: ConversationService

    @route("/share/<string:share_id>/messages", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_share_conversation.yaml"))
    def get_share_conversation(self, share_id: str) -> Response:
        """获取分享对话的消息列表。

        Args:
            share_id (str): 分享对话的唯一标识符

        Returns:
            Response: 包含消息列表的成功响应，或当消息不存在时返回404错误响应

        """
        # 通过conversation_service获取指定share_id的分享对话消息
        messages = self.conversation_service.get_share_conversation(share_id)
        # 如果消息不存在，返回404错误响应
        if messages is None:
            return not_found_message_json()

        # 返回包含消息列表的成功响应
        return success_json({"messages": messages})

    @route("/generate_share_conversation", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/generate_share_conversation.yaml"))
    @login_required
    def generate_share_conversation(self) -> Response:
        """生成分享对话

        通过请求参数生成一个分享对话，返回分享ID

        Returns:
            Response: 包含share_id的成功响应，或验证失败的错误响应

        """
        req = GenerateShareConversationReq()
        if not req.validate():
            return validate_error_json(req.errors)

        share_id = self.conversation_service.generate_share_conversation(req)

        return success_json({"share_id": share_id})

    @route("/<uuid:app_id>/<uuid:message_id>/delete", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/delete_message_by_id.yaml"))
    @login_required
    def delete_message_by_id(self, app_id: UUID, message_id: UUID) -> Response:
        self.get_app(app_id)

        self.app_service.delete_message_by_id(message_id)

        return success_message_json("删除对话消息成功")

    @route("/<uuid:app_id>/copy", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/copy_app.yaml"))
    @login_required
    def copy_app(self, app_id: UUID) -> Response:
        """复制应用

        Args:
            app_id (UUID): 要复制的应用ID

        Returns:
            Response: 包含新应用ID的成功响应

        """
        app = self.app_service.copy_app(app_id, current_user)

        return success_json({"app_id": app.id})

    @route("/create", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/create_app.yaml"))
    @login_required
    def create_app(self) -> str:
        """创建新的应用

        通过POST请求创建一个新的应用实例。需要用户登录后才能访问。
        请求体需要包含创建应用所需的信息，通过CreateAppReq进行验证。

        Returns:
            str: JSON格式的响应字符串，包含新创建应用的ID

        """
        req = CreateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        app = self.app_service.create_app(req, current_user)

        return success_json({"id": app.id})

    @route("/<uuid:app_id>", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_app.yaml"))
    @login_required
    def get_app(self, app_id: UUID) -> str:
        """获取指定应用的信息

        通过GET请求获取指定ID的应用详细信息。需要用户登录后才能访问。
        返回的信息经过GetAppResp模式化处理。

        Args:
            app_id (UUID): 要查询的应用的唯一标识符

        Returns:
            str: JSON格式的响应字符串，包含应用的详细信息

        """
        app: App = self.app_service.get_app(app_id, current_user)

        resp = GetAppResp()

        return success_json(resp.dump(app))

    @route("/<uuid:app_id>", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/update_app.yaml"))
    @login_required
    def update_app(self, app_id: UUID) -> str:
        """更新指定的应用信息

        Args:
            app_id (UUID): 要更新的应用的唯一标识符

        Returns:
            str: JSON格式的响应消息，包含更新操作的结果

        Raises:
            ValidationError: 当请求数据验证失败时

        """
        req = UpdateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.update_app(app_id, current_user, **req.data)

        return success_message_json("更新 Agent 智能体应用成功")

    @route("/<uuid:app_id>/delete", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/delete_app.yaml"))
    @login_required
    def delete_app(self, app_id: UUID) -> str:
        """删除指定的应用

        Args:
            app_id (UUID): 要删除的应用的唯一标识符

        Returns:
            str: 包含成功消息的JSON响应字符串

        Raises:
            可能抛出相关的业务异常，如应用不存在、无权限等

        """
        # 调用服务层删除应用
        self.app_service.delete_app(app_id, current_user)

        # 返回删除成功的响应消息
        return success_message_json("删除 Agent 智能体应用成功")

    @route("", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_apps_with_page.yaml"))
    @login_required
    def get_apps_with_page(self) -> Response:
        req = GetAppsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        apps, paginator = self.app_service.get_apps_with_page(req, current_user)

        resp = GetAppsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(apps), paginator=paginator))

    @route("/<uuid:app_id>/draft-config", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_draft_app_config.yaml"))
    @login_required
    def get_draft_app_config(self, app_id: UUID) -> Response:
        """获取应用的草稿配置信息

        Args:
            app_id (UUID): 应用的唯一标识符

        Returns:
            Response: 包含草稿配置信息的成功响应

        Note:
            需要用户登录才能访问此接口

        """
        draft_config = self.app_service.get_draft_app_config(app_id, current_user)

        return success_json(draft_config)

    @route("/<uuid:app_id>/draft-config", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/update_draft_app_config.yaml"))
    @login_required
    def update_draft_app_config(self, app_id: UUID) -> Response:
        """更新应用的草稿配置

        Args:
            app_id (UUID): 应用的唯一标识符

        Returns:
            Response: 包含更新成功消息的响应对象

        """
        draft_app_config = request.get_json(force=True, silent=True) or {}

        self.app_service.update_draft_app_config(app_id, draft_app_config, current_user)

        return success_message_json("更新应用草稿配置成功")

    @route("/<uuid:app_id>/publish", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/publish.yaml"))
    @login_required
    def publish(self, app_id: UUID) -> Response:
        """发布应用配置

        Args:
            app_id (UUID): 应用ID

        Returns:
            Response: 包含发布成功消息的响应

        Raises:
            PermissionError: 当用户没有权限发布应用时
            ValueError: 当应用ID无效时

        """
        self.app_service.publish_draft_app_config(app_id, current_user)

        return success_message_json("发布应用成功")

    @route("/<uuid:app_id>/publish/cancel", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/cancel_publish.yaml"))
    @login_required
    def cancel_publish(self, app_id: UUID) -> Response:
        """取消发布应用配置接口

        Args:
            app_id (UUID): 应用ID，用于标识要取消发布的应用

        Returns:
            Response: JSON响应，包含操作结果信息

        """
        self.app_service.cancel_publish_app_config(app_id, current_user)

        return success_message_json("取消发布应用成功")

    @route("/<uuid:app_id>/publish/histories", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_publish_histories_with_page.yaml"))
    @login_required
    def get_publish_histories_with_page(self, app_id: UUID) -> Response:
        """获取应用发布历史记录（分页）

        Args:
            app_id (UUID): 应用ID，用于标识要查询发布历史的应用

        Returns:
            Response: JSON响应，包含分页的发布历史记录数据
                - list: 发布历史记录列表
                - paginator: 分页信息（总数、当前页、每页大小等）

        Raises:
            401: 用户未登录
            404: 应用不存在
            400: 请求参数验证失败

        Note:
            - 需要用户登录才能访问此接口
            - 支持分页查询，通过请求参数控制页码和每页大小
            - 返回的数据按发布时间倒序排列
            - 包含每个版本的详细信息（版本号、发布时间、发布人等）

        """
        req = GetPublishHistoriesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        app_config_versions, paginator = (
            self.app_service.get_publish_histories_with_page(app_id, req, current_user)
        )

        resp = GetPublishHistoriesWithPageResp(many=True)

        return success_json(
            PageModel(list=resp.dump(app_config_versions), paginator=paginator),
        )

    @route("/<uuid:app_id>/fallback/history", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/fallback_history_to_draft.yaml"))
    @login_required
    def fallback_history_to_draft(self, app_id: UUID) -> Response:
        """将历史版本回退到草稿配置接口

        Args:
            app_id (UUID): 应用ID，用于标识要操作的应用

        Returns:
            Response: JSON响应，包含操作结果信息

        Raises:
            401: 用户未登录
            404: 应用或历史版本不存在
            400: 请求参数验证失败
            403: 用户没有操作权限

        Note:
            - 需要用户登录才能访问此接口
            - 需要在请求参数中指定要回退的历史版本ID
            - 会将指定历史版本的配置内容复制到草稿配置
            - 草稿配置会被完全覆盖，原有草稿内容将丢失
            - 操作成功后返回成功消息

        """
        req = FallbackHistoryToDraftReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.fallback_history_to_draft(
            app_id,
            req,
            current_user,
        )

        return success_message_json("回退历史配置到草稿成功")

    @route("/<uuid:app_id>/conversation/summary", methods=["GET"])
    @swag_from(get_swagger_path("app_handler/get_debug_conversation_summary.yaml"))
    @login_required
    def get_debug_conversation_summary(self, app_id: UUID) -> Response:
        """获取指定应用的调试对话摘要信息

        Args:
            app_id (UUID): 应用的唯一标识符

        Returns:
            Response: 包含对话摘要的成功响应，格式为:
                {
                    "message": "success",
                    "data": {
                        "summary": "对话摘要内容"
                    }
                }

        """
        summary = self.app_service.get_debug_conversation_summary(app_id, current_user)

        return success_json({"summary": summary})

    @route("/<uuid:app_id>/conversation/summary/update", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/update_debug_conversation_summary.yaml"))
    @login_required
    def update_debug_conversation_summary(self, app_id: UUID) -> Response:
        """更新调试对话的摘要信息

        Args:
            app_id (UUID): 应用程序的唯一标识符

        Returns:
            Response: 包含操作结果的响应对象
                - 成功时返回成功消息
                - 验证失败时返回验证错误信息

        处理流程：
            1. 验证请求数据
            2. 调用服务层更新摘要信息
            3. 返回操作结果

        """
        req = UpdateDebugConversationSummaryReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.update_debug_conversation_summary(
            app_id,
            req.summary.data,
            current_user,
        )

        return success_message_json("更新调试对话长期记忆成功")

    @route("/<uuid:app_id>/conversation/summary/delete", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/delete_debug_conversation_summary.yaml"))
    @login_required
    def delete_debug_conversation_summary(self, app_id: UUID) -> Response:
        """删除指定应用的调试对话摘要

        Args:
            app_id (UUID): 应用ID

        Returns:
            Response: 包含操作结果消息的响应对象

        """
        self.app_service.delete_debug_conversation_summary(
            app_id,
            current_user,
        )

        return success_message_json("删除调试对话长期记忆成功")

    @route("/<uuid:app_id>/debug", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/debug_chat.yaml"))
    @login_required
    def debug_chat(self, app_id: UUID) -> Response:
        """处理调试聊天请求。

        Args:
            app_id (UUID): 应用程序的唯一标识符

        Returns:
            Response: 包含调试聊天结果的响应对象

        Raises:
            ValidationError: 当请求数据验证失败时

        """
        req = DebugChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        response = self.app_service.debug_chat(app_id, req.query.data, current_user)

        return compact_generate_response(response)

    @route("/<uuid:app_id>/debug/<uuid:task_id>/stop", methods=["POST"])
    @swag_from(get_swagger_path("app_handler/stop_debug_chat.yaml"))
    @login_required
    def stop_debug_chat(self, app_id: UUID, task_id: UUID) -> Response:
        """停止调试对话

        Args:
            app_id (UUID): 应用ID
            task_id (UUID): 调试任务ID

        Returns:
            Response: 包含成功消息的响应对象

        """
        self.app_service.stop_debug_chat(app_id, task_id, current_user)

        return success_message_json("停止调试对话成功")

    @route("/<uuid:app_id>/debug/conversations", methods=["GET"])
    @swag_from(
        get_swagger_path("app_handler/get_debug_conversation_messages_with_page.yaml"),
    )
    @login_required
    def get_debug_conversation_messages_with_page(self, app_id: UUID) -> Response:
        """获取指定应用的调试对话消息分页列表

        Args:
            app_id (UUID): 应用ID

        Returns:
            Response: 包含分页消息列表的响应对象

        """
        # 解析请求参数
        req = GetDebugConversationMessagesWithPageReq(request.args)
        # 验证请求参数
        if not req.validate():
            return validate_error_json(req.errors)

        # 获取分页消息数据和分页器
        messages, paginator = (
            self.app_service.get_debut_conversation_messages_with_page(
                app_id,
                req,
                current_user,
            )
        )

        # 准备响应数据结构
        resp = GetDebugConversationMessagesWithPageResp(many=True)

        # 返回包含分页消息列表的成功响应
        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @route("/<uuid:app_id>/debug/conversations/delete", methods=["POST"])
    @swag_from(
        get_swagger_path("app_handler/delete_debug_conversations.yaml"),
    )
    @login_required
    def delete_debug_conversations(self, app_id: UUID) -> Response:
        """删除应用的调试对话记录

        Args:
            app_id (UUID): 应用ID

        Returns:
            Response: 包含成功消息的响应对象

        """
        # 调用服务层删除调试对话记录
        self.app_service.delete_debug_conversations(app_id, current_user)

        # 返回删除成功的响应消息
        return success_message_json("清空调试对话记录成功")

    @route("/ping", methods=["GET"])
    def ping(self) -> Response:
        model_class = self.llm_model_manager.get_model_class_by_provider_and_model(
            "deepseek",
            "deepseek-chat",
        )
        llm = model_class(model="deepseek-chat")
        return success_message_json(llm.invoke("你好!").content)
