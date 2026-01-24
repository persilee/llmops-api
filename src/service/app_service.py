import io
import json
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Thread
from typing import Any
from uuid import UUID

import requests
from flask import current_app
from injector import inject
from langchain.messages import HumanMessage
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
from langchain_openai import ChatOpenAI
from redis import Redis
from sqlalchemy import func
from werkzeug.datastructures import FileStorage

from pkg.paginator.paginator import Paginator
from pkg.response.http_code import HTTP_STATUS_OK
from pkg.sqlalchemy import SQLAlchemy
from src.core.agent.agents.agent_queue_manager import AgentQueueManager
from src.core.agent.agents.function_call_agent import FunctionCallAgent
from src.core.agent.agents.react_agent import ReACTAgent
from src.core.agent.entities.agent_entity import AgentConfig
from src.core.agent.entities.queue_entity import QueueEvent
from src.core.llm_model.entities.model_entity import ModelFeature, ModelParameterType
from src.core.llm_model.llm_model_manager import LLMModelManager
from src.core.memory.token_buffer_memory import TokenBufferMemory
from src.core.tools.builtin_tools.providers.builtin_provider_manager import (
    BuiltinProviderManager,
)
from src.core.tools.providers.api_provider_manager import ApiProviderManager
from src.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from src.entity.app_entity import (
    DEFAULT_APP_CONFIG,
    GENERATE_ICON_PROMPT_TEMPLATE,
    MAX_DATASET_COUNT,
    MAX_DIALOG_ROUNDS,
    MAX_OPENING_QUESTIONS_COUNT,
    MAX_OPENING_STATEMENT_LENGTH,
    MAX_PRESET_PROMPT_LENGTH,
    MAX_RETRIEVAL_COUNT,
    MAX_REVIEW_KEYWORDS_COUNT,
    MAX_TOOL_COUNT,
    AppConfigType,
    AppStatus,
)
from src.entity.conversation_entity import InvokeFrom, MessageStatus
from src.entity.dataset_entity import RetrievalSource
from src.exception.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from src.lib.helper import get_value_type, remove_fields
from src.model import App
from src.model.account import Account
from src.model.api_tool import ApiTool
from src.model.app import AppConfig, AppConfigVersion, AppDatasetJoin
from src.model.conversation import Conversation, Message
from src.model.dataset import Dataset
from src.schemas.app_schema import (
    CreateAppReq,
    FallbackHistoryToDraftReq,
    GetAppsWithPageReq,
    GetDebugConversationMessagesWithPageReq,
    GetPublishHistoriesWithPageReq,
)
from src.service.app_config_service import AppConfigService
from src.service.base_service import BaseService
from src.service.conversation_service import AgentThoughtConfig, ConversationService
from src.service.cos_service import CosService
from src.service.llm_model_service import LLMModelService
from src.service.retrieval_service import RetrievalConfig, RetrievalService


@inject
@dataclass
class AppService(BaseService):
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    api_provider_manager: ApiProviderManager
    retrieval_service: RetrievalService
    redis_client: Redis
    conversation_service: ConversationService
    app_config_service: AppConfigService
    cos_service: CosService
    llm_model_service: LLMModelService
    llm_model_manager: LLMModelManager

    def auto_create_app(self, name: str, description: str, account_id: UUID) -> None:
        """根据传递的应用名称、描述、账号id利用AI创建一个Agent智能体"""
        # 1.创建LLM，用于生成icon提示与预设提示词
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8)

        # 2.创建DallEApiWrapper包装器
        dalle_api_wrapper = DallEAPIWrapper(model="dall-e-3", size="1024x1024")

        # 3.构建生成icon链
        generate_icon_chain = (
            ChatPromptTemplate.from_template(GENERATE_ICON_PROMPT_TEMPLATE)
            | llm
            | StrOutputParser()
            | dalle_api_wrapper.run
        )

        # 4.生成预设prompt链
        generate_preset_prompt_chain = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", OPTIMIZE_PROMPT_TEMPLATE),
                    ("human", "应用名称: {name}\n\n应用描述: {description}"),
                ],
            )
            | llm
            | StrOutputParser()
        )

        # 5.创建并行链同时执行两条链
        generate_app_config_chain = RunnableParallel(
            {
                "icon": generate_icon_chain,
                "preset_prompt": generate_preset_prompt_chain,
            },
        )
        app_config = generate_app_config_chain.invoke(
            {"name": name, "description": description},
        )

        # 6.将图片下载到本地后上传到腾讯云cos中
        try:
            icon_response = requests.get(
                app_config.get("icon"),
                timeout=(3.05, 27),  # 连接超时3.05秒，读取超时27秒
            )
            if icon_response.status_code == HTTP_STATUS_OK:
                icon_content = icon_response.content
            else:
                error_msg = f"获取应用icon图标出错: {icon_response.status_code}"
                raise FailException(error_msg)
        except requests.exceptions.Timeout as e:
            error_msg = "获取应用icon图标超时，请重试"
            raise FailException(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"获取应用icon图标失败: {e!s}"
            raise FailException(error_msg) from e

        account = self.db.session.query(Account).get(account_id)
        upload_file = self.cos_service.upload_file = self.cos_service.upload_file(
            FileStorage(io.BytesIO(icon_content), filename="icon.png"),
            is_public=True,
            account=account,
        )
        icon = self.cos_service.get_file_url(upload_file.key)

        # 7.开启数据库自动提交上下文
        with self.db.auto_commit():
            # 8.创建应用记录并刷新数据，从而可以拿到应用id
            app = App(
                account_id=account.id,
                name=name,
                icon=icon,
                description=description,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 9.添加草稿记录
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **{
                    **DEFAULT_APP_CONFIG,
                    "preset_prompt": app_config.get("preset_prompt", ""),
                },
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 10.更新应用配置id
            app.draft_app_config_id = app_config_version.id

    def copy_app(self, app_id: UUID, account: Account) -> App:
        """复制应用。

        Args:
            app_id (UUID): 要复制的应用ID
            account (Account): 执行复制操作的账户信息

        Returns:
            App: 新创建的应用对象，包含复制的配置信息

        Raises:
            NotFoundException: 当原应用不存在时抛出
            ForbiddenException: 当账户无权访问原应用时抛出

        Note:
            - 新应用的状态将设置为草稿状态(DRAFT)
            - 新应用的配置版本从1开始
            - 原应用的调试对话记录不会被复制
            - 使用数据库事务确保操作的原子性

        """
        # 获取要复制的原应用信息
        app = self.get_app(app_id, account)
        # 获取原应用的草稿配置
        draft_app_config = app.draft_app_config

        # 创建应用对象的字典副本
        app_dict = app.__dict__.copy()
        app_name = app_dict["name"] + "(副本)"
        # 创建草稿配置对象的字典副本
        draft_app_config_dict = draft_app_config.__dict__.copy()

        # 定义需要从应用对象中移除的字段列表
        app_remove_fields = [
            "id",  # 应用ID，需要重新生成
            "name",  # 应用名称，需要重新生成
            "app_config_id",  # 应用配置ID，需要重新生成
            "draft_app_config_id",  # 草稿配置ID，需要重新生成
            "debug_conversation_id",  # 调试对话ID，需要重新生成
            "status",  # 应用状态，新应用默认为草稿状态
            "updated_at",  # 更新时间，需要重新生成
            "created_at",  # 创建时间，需要重新生成
            "_sa_instance_state",  # SQLAlchemy实例状态，需要移除
        ]
        # 定义需要从草稿配置对象中移除的字段列表
        draft_app_config_remove_fields = [
            "id",  # 配置ID，需要重新生成
            "app_id",  # 应用ID，需要重新关联
            "version",  # 版本号，新配置从1开始
            "updated_at",  # 更新时间，需要重新生成
            "created_at",  # 创建时间，需要重新生成
            "_sa_instance_state",  # SQLAlchemy实例状态，需要移除
        ]
        # 从应用字典中移除指定字段
        remove_fields(app_dict, app_remove_fields)
        # 从草稿配置字典中移除指定字段
        remove_fields(draft_app_config_dict, draft_app_config_remove_fields)

        # 使用数据库事务上下文，确保操作的原子性
        with self.db.auto_commit():
            # 创建新的应用实例，状态设置为草稿
            new_app = App(
                **app_dict,
                status=AppStatus.DRAFT,
                name=app_name,
            )
            # 将新应用添加到数据库会话
            self.db.session.add(new_app)
            # 刷新会话，获取新应用的ID
            self.db.session.flush()

            # 创建新的草稿配置实例
            new_draft_app_config = AppConfigVersion(
                **draft_app_config_dict,
                app_id=new_app.id,  # 关联新应用的ID
                version=1,  # 版本号从1开始
            )
            # 将新草稿配置添加到数据库会话
            self.db.session.add(new_draft_app_config)
            # 刷新会话，获取新配置的ID
            self.db.session.flush()

            # 建立新应用和新草稿配置的关联
            new_app.draft_app_config_id = new_draft_app_config.id

        # 返回新创建的应用对象
        return new_app

    def get_apps_with_page(
        self,
        req: GetAppsWithPageReq,
        account: Account,
    ) -> tuple[list[App], Paginator]:
        """获取应用列表（分页）。

        Args:
            req: 分页查询请求参数，包含页码、每页数量、搜索关键词等信息
            account: 当前用户账户信息，用于权限验证

        Returns:
            tuple[list[App], Paginator]: 返回一个元组，包含：
                - 应用列表：当前页的应用对象列表
                - 分页器：包含分页相关信息的对象

        Note:
            - 支持按应用名称进行模糊搜索
            - 查询结果按创建时间倒序排列

        """
        # 创建分页器实例，用于处理分页查询
        paginator = Paginator(db=self.db, req=req)

        # 初始化过滤条件列表
        filters = [App.account_id == account.id]
        # 如果请求中包含搜索关键词，则添加名称模糊匹配过滤条件
        if req.search_word.data:
            filters.append(App.name.ilike(f"%{req.search_word.data}%"))

        # 执行分页查询：
        # 1. 查询应用表
        # 2. 应用过滤条件
        # 3. 按创建时间倒序排列
        apps = paginator.paginate(
            self.db.session.query(App).filter(*filters).order_by(App.created_at.desc()),
        )

        # 返回查询结果和分页器信息
        return apps, paginator

    def delete_message_by_id(self, message_id: UUID) -> Message:
        """根据消息ID删除消息

        Args:
            message_id: 消息ID

        Returns:
            Message: 删除后的消息对象

        """
        # 根据消息ID查询消息
        message = self.get(Message, message_id)
        if message is None:
            error_message = f"消息ID为{message_id}的消息不存在"
            raise FailException(error_message)
        # 如果消息存在，则删除
        self.delete(message)

        return message

    def delete_debug_conversations(self, app_id: UUID, account: Account) -> App:
        """删除应用的调试对话记录

        Args:
            app_id: 应用ID
            account: 账户信息

        Returns:
            App: 更新后的应用对象

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)

        # 如果应用没有调试对话记录，直接返回
        if not app.debug_conversation_id:
            return app

        # 清空应用的调试对话ID
        self.update(app, debug_conversation_id=None)

        return app

    def get_debut_conversation_messages_with_page(
        self,
        app_id: UUID,
        req: GetDebugConversationMessagesWithPageReq,
        account: Account,
    ) -> tuple[list[Message], Paginator]:
        """获取应用的调试对话消息列表，支持分页查询。

        Args:
            app_id (UUID): 应用ID
            req (GetDebugConversationMessagesWithPageReq): 分页请求参数，包含页码、
            每页数量等信息
            account (Account): 当前用户账户信息

        Returns:
            tuple[list[Message], Paginator]: 返回一个元组，包含：
                - 消息列表，按创建时间倒序排列
                - 分页器对象，包含分页相关信息

        Raises:
            NotFoundException: 当应用不存在时抛出
            ForbiddenException: 当用户无权访问该应用时抛出

        Note:
            查询的消息满足以下条件：
            1. 属于指定应用的调试对话
            2. 消息状态为正常或已停止
            3. 消息内容不为空
            4. 如果请求中指定了创建时间过滤条件，则消息创建时间需要满足该条件

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)

        # 获取应用的调试对话记录
        debug_conversation = app.debug_conversation

        # 创建分页器实例，用于处理分页查询
        paginator = Paginator(db=self.db, req=req)
        filters = []
        # 如果请求中包含创建时间过滤条件，则添加时间过滤
        if req.created_at.data:
            created_at_datetime = datetime.fromtimestamp(req.created_at.data, tz=UTC)
            filters.append(Message.created_at <= created_at_datetime)

        # 执行分页查询，获取消息列表
        # 查询条件包括：
        # 1. 属于指定调试对话
        # 2. 消息状态为正常(不返回已停止的消息)
        # 3. 消息内容不为空
        # 4. 满足时间过滤条件（如果有）
        # 按创建时间倒序排列
        messages = paginator.paginate(
            self.db.session.query(Message)
            .filter(
                Message.conversation_id == debug_conversation.id,
                Message.status.in_([MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            )
            .order_by(Message.created_at.desc()),
        )

        # 返回消息列表和分页器信息
        return messages, paginator

    def stop_debug_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        """停止调试对话

        Args:
            app_id (UUID): 应用ID
            task_id (UUID): 任务ID，用于标识需要停止的调试对话任务
            account (Account): 账户信息，用于验证权限

        Returns:
            None

        """
        # 获取应用信息，验证应用存在性和所有权
        self.get_app(app_id, account)

        # 设置停止标志，终止指定的调试对话任务
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def debug_chat(self, app_id: UUID, query: str, account: Account) -> Generator:
        """处理应用的调试对话功能。

        该方法实现了应用的调试对话功能，包括：
        1. 验证应用权限和获取配置
        2. 初始化LLM模型和对话记忆
        3. 配置工具集（内置工具、API工具和知识库检索）
        4. 创建并运行智能智能体
        5. 处理对话事件流
        6. 异步保存对话记录

        Args:
            app_id (UUID): 应用ID，用于标识具体的应用
            query (str): 用户输入的查询内容
            account (Account): 当前用户账户信息，用于权限验证

        Yields:
            str: 服务器发送事件格式的响应数据，包含对话过程中的各种事件信息

        Raises:
            NotFoundException: 当应用不存在时抛出
            ForbiddenException: 当用户无权访问应用时抛出

        Note:
            - 使用TokenBufferMemory管理对话历史
            - 支持多种工具类型：内置工具、API工具和知识库检索
            - 采用FunctionCallAgent处理对话流程
            - 使用异步线程保存对话记录，提高响应性能

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)

        # 获取应用的草稿配置
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 获取应用的调试对话记录
        debug_conversation = app.debug_conversation

        # 初始化ChatOpenAI模型实例
        llm = self.llm_model_service.load_language_model(
            draft_app_config.get("model_config", {}),
        )

        # 创建一条消息记录
        message = self.create(
            Message,
            app_id=app_id,
            conversation_id=debug_conversation.id,
            invoke_from=InvokeFrom.DEBUGGER,
            created_by=account.id,
            query=query,
            status=MessageStatus.NORMAL,
        )

        # 创建令牌缓冲记忆实例，用于管理对话历史
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )

        # 获取历史对话消息，限制消息数量为配置的对话轮次
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        # 根据草稿配置中的工具配置，获取对应的LangChain工具实例
        tools = self.app_config_service.get_langchain_tools_by_config(
            draft_app_config["tools"],
        )

        # 如果配置了知识库，创建知识库检索工具
        if draft_app_config["datasets"]:
            # 创建检索配置实例
            retrieval_config = RetrievalConfig(
                flask_app=current_app._get_current_object(),  # noqa: SLF001
                dataset_ids=[dataset["id"] for dataset in draft_app_config["datasets"]],
                account_id=account.id,
                retrieval_source=RetrievalSource.APP,
                **draft_app_config["retrieval_config"],
            )
            # 创建知识库检索工具
            dataset_retrieval = (
                self.retrieval_service.create_langchain_tool_from_search(
                    retrieval_config,
                )
            )
            # 将知识库检索工具添加到工具列表
            tools.append(dataset_retrieval)

        # 根据LLM模型特性选择合适的Agent类：
        # - 如果模型支持工具调用功能，使用FunctionCallAgent
        # - 否则使用ReACTAgent
        agent_class = (
            FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
        )
        # 创建FunctionCallAgent实例
        agent = agent_class(
            name="debug_agent",
            llm=llm,
            # 创建智能体配置
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.DEBUGGER,
                preset_prompt=draft_app_config["preset_prompt"],
                enable_long_term_memory=draft_app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=draft_app_config["review_config"],
            ),
        )

        # 初始化智能体思考记录字典，用于存储对话过程中的思考过程
        agent_thoughts = {}

        # 运行智能体并处理事件流
        for agent_thought in agent.stream(
            {
                "messages": [HumanMessage(query)],
                "history": history,
                "long_term_memory": debug_conversation.summary,
            },
        ):
            event_id = str(agent_thought.id)

            if agent_thought.event != QueueEvent.PING:
                # 处理智能体消息事件，支持增量更新
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 更新已存在的记录，合并思考过程和答案
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(
                            update={
                                "thought": agent_thoughts[event_id].thought
                                + agent_thought.thought,
                                # 消息相关数据
                                "message": agent_thought.message,
                                "message_token_count": (
                                    agent_thought.message_token_count
                                ),
                                "message_unit_price": agent_thought.message_unit_price,
                                "message_price_unit": agent_thought.message_price_unit,
                                # 答案相关数据
                                "answer": agent_thoughts[event_id].answer
                                + agent_thought.answer,
                                "answer_token_count": agent_thought.answer_token_count,
                                "answer_unit_price": agent_thought.answer_unit_price,
                                "answer_price_unit": agent_thought.answer_price_unit,
                                # Agent推理统计相关
                                "total_token_count": agent_thought.total_token_count,
                                "total_price": agent_thought.total_price,
                                "latency": agent_thought.latency,
                            },
                        )
                else:
                    # 处理其他类型的事件
                    agent_thoughts[event_id] = agent_thought

            # 构建事件数据，包含对话过程中的所有相关信息
            data = {
                **agent_thought.model_dump(
                    include={
                        "event",
                        "thought",
                        "observation",
                        "tool",
                        "tool_input",
                        "answer",
                        "latency",
                        "total_token_count",
                        "total_price",
                    },
                ),
                "id": event_id,
                "conversation_id": str(debug_conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }

            # 生成服务器发送事件格式的响应
            yield f"event: {agent_thought.event.value}\ndata: {json.dumps(data)}\n\n"

        # 创建异步线程保存智能体思考记录，避免阻塞主流程
        agent_thought_config = AgentThoughtConfig(
            flask_app=current_app._get_current_object(),  # noqa: SLF001
            account_id=account.id,
            app_id=app_id,
            app_config=draft_app_config,
            conversation_id=debug_conversation.id,
            message_id=message.id,
            agent_thoughts=list(agent_thoughts.values()),
        )
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={"config": agent_thought_config},
        )

        # 启动线程
        thread.start()

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """获取应用的调试对话摘要

        Args:
            app_id (UUID): 应用ID，用于标识要查询的应用
            account (Account): 当前操作用户的账户信息

        Returns:
            str: 调试对话的摘要文本

        Raises:
            NotFoundException: 当应用不存在时抛出
            PermissionError: 当用户没有访问该应用的权限时抛出
            FailException: 当应用的长时记忆功能未开启时抛出

        Note:
            - 会验证用户是否有权限访问该应用
            - 检查应用的草稿配置中是否开启了长时记忆功能
            - 只有在长时记忆功能开启时才能获取对话摘要
            - 返回的是调试对话的摘要信息

        """
        app = self.get_app(app_id, account)

        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            error_msg = "长时记忆未开启"
            raise FailException(error_msg)

        return app.debug_conversation.summary

    def update_debug_conversation_summary(
        self,
        app_id: UUID,
        summary: str,
        account: Account,
    ) -> Conversation:
        """更新应用的调试对话摘要

        Args:
            app_id (UUID): 应用ID，用于标识要更新的应用
            summary (str): 新的对话摘要内容
            account (Account): 当前操作用户的账户信息

        Returns:
            Conversation: 更新后的对话对象

        Raises:
            NotFoundException: 当应用不存在时抛出
            PermissionError: 当用户没有访问该应用的权限时抛出
            FailException: 当应用的长时记忆功能未开启时抛出

        Note:
            - 会验证用户是否有权限访问该应用
            - 检查应用的草稿配置中是否开启了长时记忆功能
            - 只有在长时记忆功能开启时才能更新对话摘要
            - 会更新调试对话的摘要内容
            - 返回更新后的对话对象

        """
        app = self.get_app(app_id, account)

        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            error_msg = "长时记忆未开启"
            raise FailException(error_msg)

        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation_summary(self, app_id: UUID, account: Account) -> App:
        """删除应用的调试对话

        Args:
            app_id (UUID): 应用ID，用于标识要删除调试对话的应用
            account (Account): 当前操作用户的账户信息

        Returns:
            App: 更新后的应用对象

        Raises:
            NotFoundException: 当应用不存在时抛出
            PermissionError: 当用户没有访问该应用的权限时抛出

        Note:
            - 会验证用户是否有权限访问该应用
            - 如果应用没有关联的调试对话，直接返回应用对象
            - 通过将debug_conversation_id设置为None来删除调试对话关联
            - 返回更新后的应用对象

        """
        app = self.get_app(app_id, account)

        if not app.debug_conversation_id:
            return app

        self.update(app, debug_conversation_id=None)

        return app

    def fallback_history_to_draft(
        self,
        app_id: UUID,
        req: FallbackHistoryToDraftReq,
        account: Account,
    ) -> AppConfigVersion:
        """将历史版本回退到草稿配置

        Args:
            app_id (UUID): 应用ID，用于标识要操作的应用
            req (FallbackHistoryToDraftReq): 回退请求参数，包含要回退的版本ID
            account (Account): 当前操作用户的账户信息

        Returns:
            AppConfigVersion: 更新后的草稿配置版本对象

        Raises:
            NotFoundException: 当应用或配置版本不存在时抛出
            PermissionError: 当用户没有操作权限时抛出
            ValidationError: 当配置数据验证失败时抛出

        Note:
            - 会验证用户是否有权限访问该应用
            - 验证指定的历史版本是否存在
            - 复制历史版本的配置数据到草稿配置
            - 移除不需要的字段（如id、版本号、时间戳等）
            - 对配置数据进行验证
            - 更新草稿配置记录，并记录更新时间

        """
        app = self.get_app(app_id, account)

        app_config_version = self.get(AppConfigVersion, req.app_config_version_id.data)
        if not app_config_version:
            error_msg = "该应用配置版本不存在"
            raise NotFoundException(error_msg)

        # 复制草稿配置数据，准备创建版本记录
        draft_app_config_copy = app_config_version.__dict__.copy()

        # 移除不需要的字段
        remove_fields(
            draft_app_config_copy,
            [
                "id",
                "app_id",
                "version",
                "config_type",
                "updated_at",
                "created_at",
                "_sa_instance_state",
            ],
        )

        # 验证草稿配置数据
        draft_app_config_dict = self._validate_draft_app_config(
            draft_app_config_copy,
            account,
        )

        # 更新草稿配置记录
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            updated_at=datetime.now(UTC),
            **draft_app_config_dict,
        )

        return draft_app_config_dict

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """取消发布应用的草稿配置。

        将应用的状态设置为草稿状态，并删除应用配置记录。

        Args:
            app_id: 应用ID
            account: 账户信息

        """
        app = self.get_app(app_id, account)
        if app.status != AppStatus.PUBLISHED:
            error_msg = "应用未发布，无法取消发布"
            raise FailException(error_msg)

        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        return app

    def get_publish_histories_with_page(
        self,
        app_id: UUID,
        req: GetPublishHistoriesWithPageReq,
        account: Account,
    ) -> tuple[list[AppConfigVersion], Paginator]:
        """获取应用的发布历史记录（分页查询）

        Args:
            app_id (UUID): 应用ID，用于标识要查询的应用
            req (GetPublishHistoriesWithPageReq): 分页请求参数，包含页码、每页大小等信息
            account (Account): 当前操作用户的账户信息

        Returns:
            tuple[list[AppConfigVersion], Paginator]:
                - list[AppConfigVersion]: 应用配置版本列表，按版本号降序排列
                - Paginator: 分页器对象，包含分页相关信息

        Raises:
            NotFoundError: 当应用不存在时抛出
            PermissionError: 当用户没有访问该应用的权限时抛出

        Note:
            - 只返回已发布状态(PUBLISHED)的配置版本
            - 结果按版本号降序排列，最新版本在前
            - 使用分页器处理分页逻辑
            - 会验证用户是否有权限访问该应用

        """
        self.get_app(app_id, account)

        paginator = Paginator(db=self.db, req=req)

        app_config_versions = paginator.paginate(
            self.db.session.query(AppConfigVersion)
            .filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            )
            .order_by(AppConfigVersion.version.desc()),
        )

        return app_config_versions, paginator

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """发布应用的草稿配置。

        将应用的草稿配置发布为正式配置，包括：
        - 创建新的应用配置记录
        - 更新应用状态为已发布
        - 更新知识库关联
        - 创建配置版本记录

        Args:
            app_id: 应用ID
            account: 执行操作的账户信息

        Returns:
            App: 更新后的应用对象

        Raises:
            ForbiddenException: 当账户无权操作该应用时
            NotFoundException: 当应用不存在时
            ValidateErrorException: 当草稿配置验证失败时

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)
        # 获取应用的草稿配置
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 创建新的应用配置记录
        app_config = self.create(
            AppConfig,
            app_id=app_id,
            # 设置模型配置
            model_config=draft_app_config["model_config"],
            # 设置对话轮次配置
            dialog_round=draft_app_config["dialog_round"],
            # 设置预设提示词
            preset_prompt=draft_app_config["preset_prompt"],
            # 处理工具配置，转换为标准格式
            tools=[
                {
                    "type": tool["type"],
                    "provider_id": tool["provider"]["id"],
                    "tool_id": tool["tool"]["name"],
                    "params": tool["tool"]["params"],
                }
                for tool in draft_app_config["tools"]
            ],
            # 设置工作流配置
            workflows=draft_app_config["workflows"],
            # 设置检索配置
            retrieval_config=draft_app_config["retrieval_config"],
            # 设置长期记忆配置
            long_term_memory=draft_app_config["long_term_memory"],
            # 设置开场白
            opening_statement=draft_app_config["opening_statement"],
            # 设置开场问题
            opening_questions=draft_app_config["opening_questions"],
            # 设置建议配置
            suggested_after_answer=draft_app_config["suggested_after_answer"],
            # 设置语音转文字配置
            speech_to_text=draft_app_config["speech_to_text"],
            # 设置文字转语音配置
            text_to_speech=draft_app_config["text_to_speech"],
            # 设置审核配置
            review_config=draft_app_config["review_config"],
        )

        # 更新应用状态为已发布，并关联新的配置ID
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 使用事务上下文，删除原有的知识库关联
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 创建新的知识库关联记录
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 复制草稿配置数据，准备创建版本记录
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        # 定义需要移除的字段列表
        remove_fields(
            draft_app_config_copy,
            [
                "id",
                "version",
                "config_type",
                "updated_at",
                "created_at",
                "_sa_instance_state",
            ],
        )

        # 查询当前最大的已发布版本号
        max_version = (
            self.db.session.query(
                func.coalesce(func.max(AppConfigVersion.version), 1),
            )
            .filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            )
            .scalar()
        )

        # 创建新的配置版本记录
        self.create(
            AppConfigVersion,
            # 版本号递增
            version=max_version + 1,
            # 设置配置类型为已发布
            config_type=AppConfigType.PUBLISHED,
            # 复制草稿配置的其他字段
            **draft_app_config_copy,
        )

        # 返回更新后的应用对象
        return app

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """创建新应用

        Args:
            req: 创建应用的请求参数，包含应用名称、图标、描述等信息
            account: 创建应用的用户账号信息

        Returns:
            App: 创建成功的应用对象

        """
        # 使用数据库事务上下文，确保操作的原子性
        with self.db.auto_commit():
            # 创建应用实体对象
            app = App(
                account_id=account.id,  # 关联用户ID
                name=req.name.data,  # 应用名称
                icon=req.icon.data,  # 应用图标
                description=req.description.data,  # 应用描述
                status=AppStatus.DRAFT,  # 初始状态为草稿
            )
            # 将应用对象添加到数据库会话中
            self.db.session.add(app)
            # 刷新会话，获取应用ID
            self.db.session.flush()

            # 创建应用配置版本对象
            app_config_version = AppConfigVersion(
                app_id=app.id,  # 关联应用ID
                version=1,  # 初始版本号
                config_type=AppConfigType.DRAFT,  # 配置类型为草稿
                **DEFAULT_APP_CONFIG,  # 使用默认配置
            )
            # 将配置版本对象添加到数据库会话中
            self.db.session.add(app_config_version)
            # 刷新会话，获取配置版本ID
            self.db.session.flush()

            # 将草稿配置ID关联到应用对象
            app.draft_app_config_id = app_config_version.id

        # 返回创建的应用对象
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """获取应用信息

        Args:
            app_id: 应用ID，用于唯一标识一个应用
            account: 用户账号信息，用于验证应用所有权

        Returns:
            App: 返回获取到的应用对象

        Raises:
            NotFoundException: 当应用不存在时抛出
            ForbiddenException: 当应用不属于当前用户时抛出

        """
        # 根据应用ID查询应用信息
        app = self.get(App, app_id)
        # 检查应用是否存在
        if not app:
            error_msg = f"应用 {app_id} 不存在"
            raise NotFoundException(error_msg)

        # 验证应用所有权，确保只有应用所有者才能访问
        if app.account_id != account.id:
            error_msg = f"应用 {app_id} 不属于当前用户"
            raise ForbiddenException(error_msg)

        # 返回应用对象
        return app

    def update_app(self, app_id: UUID, account: Account, **kwargs: dict) -> App:
        """更新应用信息

        Args:
            app_id: 应用ID
            account: 账户信息
            **kwargs: 要更新的应用字段键值对

        Returns:
            App: 更新后的应用对象

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)

        # 更新应用信息
        self.update(app, **kwargs)

        # 返回更新后的应用对象
        return app

    def delete_app(self, app_id: UUID, account: Account) -> App:
        """删除应用

        Args:
            app_id: 应用ID
            account: 账户信息

        Returns:
            App: 被删除的应用对象

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)

        # 删除应用
        self.delete(app)

        # 返回被删除的应用对象
        return app

    def get_draft_app_config(self, app_id: UUID, account: Account) -> dict:
        """获取应用的草稿配置信息。

        该方法会获取指定应用的草稿配置，并对配置中的工具、知识库等信息进行验证和格式化。
        主要包括：
        1. 验证内置工具和API工具的配置
        2. 验证知识库的存在性
        3. 格式化返回的配置信息

        Args:
            app_id (UUID): 应用的唯一标识符
            account (Account): 当前操作的用户账户信息

        Returns:
            dict: 包含完整草稿配置信息的字典，包括：
                - id: 配置ID
                - model_config: 模型配置
                - dialog_round: 对话轮次
                - preset_prompt: 预设提示词
                - tools: 工具配置列表
                - workflows: 工作流配置列表
                - datasets: 知识库配置列表
                - retrieval_config: 检索配置
                - long_term_memory: 长期记忆配置
                - opening_statement: 开场白
                - opening_questions: 开场问题列表
                - suggested_after_answer 对话后生成建议问题列表
                - speech_to_text: 语音转文本配置
                - text_to_speech: 文本转语音配置
                - review_config: 审核配置
                - created_at: 创建时间戳
                - updated_at: 更新时间戳

        """
        # 获取应用信息
        app = self.get_app(app_id, account)

        # 返回应用草稿配置
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(
        self,
        app_id: UUID,
        draft_app_config: dict[str, Any],
        account: Account,
    ) -> dict[str, Any]:
        """更新应用的草稿配置。

        Args:
            app_id: 应用ID
            draft_app_config: 待更新的草稿配置字典
            account: 执行更新的账户对象

        Returns:
            dict[str, Any]: 更新后的草稿配置记录

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)

        # 验证草稿配置的合法性和完整性
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 获取应用的当前草稿配置记录
        draft_app_config_record = app.draft_app_config
        # 更新草稿配置，包括更新时间和配置内容
        self.update(
            draft_app_config_record,
            updated_at=datetime.now(UTC),
            **draft_app_config,
        )

        # 返回更新后的草稿配置记录
        return draft_app_config_record

    def _validate_model_config(self, draft_model_config: dict) -> dict:  # noqa: PLR0912
        """验证并规范化模型配置。

        该方法对传入的模型配置进行全面的验证，包括：
        - 验证配置格式是否正确
        - 验证提供商和模型是否存在
        - 验证并规范化模型参数

        Args:
            draft_model_config (dict): 待验证的模型配置字典，应包含以下结构：
                {
                    "model_config": {
                        "provider": str,  # 模型提供商名称
                        "model": str,     # 模型名称
                        "parameters": dict  # 模型参数
                    }
                }

        Returns:
            dict: 验证并规范化后的模型配置字典。如果参数值无效，
                将使用默认值替换。

        Raises:
            ValidateErrorException: 当配置格式错误、提供商不存在或模型不存在时抛出。

        """
        # 检查是否存在模型配置
        if "model_config" in draft_model_config:
            model_config = draft_model_config["model_config"]
            # 验证模型配置是否为字典类型
            if not isinstance(model_config, dict):
                error_msg = "模型配置格式错误"
                raise ValidateErrorException(error_msg)
            # 验证模型配置是否包含必需的字段：provider、model、parameters
            if set(model_config.keys()) != {"provider", "model", "parameters"}:
                error_msg = "模型配置格式错误"
                raise ValidateErrorException(error_msg)
            # 验证提供商类型是否为非空字符串
            if not model_config["provider"] or not isinstance(
                model_config["provider"],
                str,
            ):
                error_msg = "模型提供商类型必须是字符串"
                raise ValidateErrorException(error_msg)
            # 获取并验证模型提供商是否存在
            provider = self.llm_model_manager.get_provider(model_config["provider"])
            if not provider:
                error_msg = "模型提供商类型不存在"
                raise ValidateErrorException(error_msg)
            # 验证模型名称是否为非空字符串
            if not model_config["model"] or not isinstance(model_config["model"], str):
                error_msg = "模型名称必须是字符串"
                raise ValidateErrorException(error_msg)
            # 获取并验证模型是否存在
            model_entity = provider.get_model_entity(model_config["model"])
            if not model_entity:
                error_msg = "模型名称不存在"
                raise ValidateErrorException(error_msg)

            # 初始化参数字典，用于存储验证后的参数
            parameters = {}
            # 遍历模型定义的所有参数
            for parameter in model_entity.parameters:
                # 从配置中获取参数值，如果不存在则使用默认值
                parameter_value = model_config["parameters"].get(
                    parameter.name,
                    parameter.default,
                )

                # 处理必填参数
                if parameter.required:
                    # 如果参数为None或类型不匹配，则使用默认值
                    if (
                        parameter_value is None
                        or get_value_type(parameter_value) != parameter.type.value
                    ):
                        parameter_value = parameter.default
                # 处理非必填参数
                elif (
                    parameter_value is not None
                    and get_value_type(parameter_value) != parameter.type.value
                ):
                    # 如果参数值不为None但类型不匹配，则使用默认值
                    parameter_value = parameter.default

                # 验证参数选项
                # 如果参数定义了可选值列表，则确保参数值在可选值范围内
                if parameter.options and parameter_value not in parameter.options:
                    parameter_value = parameter.default

                # 验证数值范围
                # 对于数值类型参数，检查是否在定义的最小值和最大值范围内
                if (
                    parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT]
                    and parameter_value is not None
                    and (
                        (parameter.min and parameter_value < parameter.min)
                        or (parameter.max and parameter_value > parameter.max)
                    )
                ):
                    parameter_value = parameter.default

                # 将验证后的参数值存入参数字典
                parameters[parameter.name] = parameter_value

            # 更新模型配置中的参数
            model_config["parameters"] = parameters
            # 更新草稿配置中的模型配置
            draft_model_config["model_config"] = model_config

        # 返回验证后的模型配置
        return draft_model_config

    def _validate_dialog_round(self, dialog_round: dict) -> dict:
        """验证对话轮数配置

        Args:
            dialog_round: 对话轮数配置

        Returns:
            dict: 验证后的对话轮数配置

        Raises:
            ValidateErrorException: 当对话轮数配置错误时抛出

        """
        if not isinstance(dialog_round, int) or not (
            0 <= dialog_round <= MAX_DIALOG_ROUNDS
        ):
            error_msg = f"对话轮数配置必须整数，应为0~{MAX_DIALOG_ROUNDS}之间的整数"
            raise ValidateErrorException(error_msg)
        return dialog_round

    def _validate_preset_prompt(self, preset_prompt: str) -> str:
        """验证预设提示词配置

        Args:
            preset_prompt: 预设提示词

        Returns:
            str: 验证后的预设提示词

        Raises:
            ValidateErrorException: 当预设提示词配置错误时抛出

        """
        if (
            not isinstance(preset_prompt, str)
            or len(preset_prompt) > MAX_PRESET_PROMPT_LENGTH
        ):
            error_msg = f"预设提示词配置格式错误, 长度应小于{MAX_PRESET_PROMPT_LENGTH}"
            raise ValidateErrorException(error_msg)
        return preset_prompt

    def _validate_tools(self, tools: list, account: Account) -> list:  # noqa: PLR0912
        """验证工具配置

        Args:
            tools: 工具配置列表
            account: 用户账户信息

        Returns:
            list: 验证后的工具配置列表

        Raises:
            ValidateErrorException: 当工具配置错误时抛出

        """
        validate_tools = []
        if not isinstance(tools, list):
            error_msg = "工具配置格式错误，应为列表"
            raise ValidateErrorException(error_msg)
        if len(tools) > MAX_TOOL_COUNT:
            error_msg = f"工具数量超过最大限制{MAX_TOOL_COUNT}"
            raise ValidateErrorException(error_msg)
        for tool in tools:
            if not tool or not isinstance(tool, dict):
                error_msg = "工具配置格式错误，应为字典"
                raise ValidateErrorException(error_msg)
            if set(tool.keys()) != {"tool_id", "type", "provider_id", "params"}:
                error_msg = "工具配置格式错误，字段不匹配"
                raise ValidateErrorException(error_msg)
            if tool["type"] not in ["builtin_tool", "api_tool"]:
                error_msg = "工具类型错误，应为builtin_tool或api_tool"
                raise ValidateErrorException(error_msg)
            if (
                not tool["provider_id"]
                or not tool["tool_id"]
                or not isinstance(tool["provider_id"], str)
                or not isinstance(tool["tool_id"], str)
            ):
                error_msg = "工具配置格式错误，provider_id或tool_id应为字符串"
                raise ValidateErrorException(error_msg)
            if not isinstance(tool["params"], dict):
                error_msg = "工具配置格式错误，params应为字典"
                raise ValidateErrorException(error_msg)
            if tool["type"] == "builtin_tool":
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider_id"],
                    tool["tool_id"],
                )
                if not builtin_tool:
                    continue
            else:
                api_tool = (
                    self.db.session.query(ApiTool)
                    .filter(
                        ApiTool.provider_id == tool["provider_id"],
                        ApiTool.id == tool["tool_id"],
                        ApiTool.account_id == account.id,
                    )
                    .one_or_none()
                )
                if not api_tool:
                    continue
            validate_tools.append(tool)

        check_tools = [
            f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools
        ]
        if len(set(check_tools)) != len(validate_tools):
            error_msg = "工具列表中存在重复的工具"
            raise ValidateErrorException(error_msg)
        return validate_tools

    def _validate_workflows(self, workflows: list) -> list:
        """验证工作流配置

        Args:
            workflows: 工作流配置列表

        Returns:
            list: 验证后的工作流配置列表

        Raises:
            ValidateErrorException: 当工作流配置错误时抛出

        """
        # TODO: 实现工作流验证逻辑
        return []

    def _validate_datasets(self, datasets: list, account: Account) -> list:
        """验证知识库配置

        Args:
            datasets: 知识库ID列表
            account: 用户账户信息

        Returns:
            list: 验证后的知识库ID列表

        Raises:
            ValidateErrorException: 当知识库配置错误时抛出

        """
        if not isinstance(datasets, list):
            error_msg = "知识库列表必须是列表类型"
            raise ValidateErrorException(error_msg)
        if len(datasets) > MAX_DATASET_COUNT:
            error_msg = f"知识库数量不能超过{MAX_DATASET_COUNT}"
            raise ValidateErrorException(error_msg)
        for dataset_id in datasets:
            try:
                UUID(dataset_id)
            except Exception as e:
                error_msg = "知识库ID必须是UUID类型"
                raise ValidateErrorException(error_msg) from e
        if len(set(datasets)) != len(datasets):
            error_msg = "知识库列表中存在重复的知识库"
            raise ValidateErrorException(error_msg)
        dataset_records = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            )
            .all()
        )
        dataset_sets = {str(dataset_record.id) for dataset_record in dataset_records}
        return [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

    def _validate_retrieval_config(self, retrieval_config: dict) -> dict:
        """验证检索配置

        Args:
            retrieval_config: 检索配置字典

        Returns:
            dict: 验证后的检索配置

        Raises:
            ValidateErrorException: 当检索配置错误时抛出

        """
        if not retrieval_config or not isinstance(retrieval_config, dict):
            error_msg = "检索配置必须是字典类型"
            raise ValidateErrorException(error_msg)
        if set(retrieval_config.keys()) != {
            "retrieval_strategy",
            "k",
            "score",
        }:
            error_msg = "检索配置必须包含检索策略、检索数量和检索分数"
            raise ValidateErrorException(error_msg)
        if retrieval_config["retrieval_strategy"] not in [
            "semantic",
            "full_text",
            "hybrid",
        ]:
            error_msg = "检索策略必须是语义检索、全文检索或混合检索"
            raise ValidateErrorException(error_msg)
        if not isinstance(retrieval_config["k"], int) or not (
            0 <= retrieval_config["k"] <= MAX_RETRIEVAL_COUNT
        ):
            error_msg = f"检索数量必须是整数，且在0到{MAX_RETRIEVAL_COUNT}之间"
            raise ValidateErrorException(error_msg)
        if not isinstance(retrieval_config["score"], float) or not (
            0 <= retrieval_config["score"] <= 1
        ):
            error_msg = "检索分数必须是浮点数，且在0到1之间"
            raise ValidateErrorException(error_msg)
        return retrieval_config

    def _validate_long_term_memory(self, long_term_memory: dict) -> dict:
        """验证长期记忆配置

        Args:
            long_term_memory: 长期记忆配置字典

        Returns:
            dict: 验证后的长期记忆配置

        Raises:
            ValidateErrorException: 当长期记忆配置错误时抛出

        """
        if not long_term_memory or not isinstance(long_term_memory, dict):
            error_msg = "长期记忆配置必须是字典"
            raise ValidateErrorException(error_msg)
        if set(long_term_memory.keys()) != {"enable"} or not isinstance(
            long_term_memory["enable"],
            bool,
        ):
            error_msg = (
                "长期记忆配置必须是包含enable键的字典，且enable的值必须是布尔类型"
            )
            raise ValidateErrorException(error_msg)
        return long_term_memory

    def _validate_suggested_after_answer(self, suggested_after_answer: dict) -> dict:
        if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
            error_msg = "用户建议问题配置必须是字典"
            raise ValidateErrorException(error_msg)
        if set(suggested_after_answer.keys()) != {"enable"} or not isinstance(
            suggested_after_answer["enable"],
            bool,
        ):
            error_msg = (
                "用户建议问题配置必须是包含enable键的字典，且enable的值必须是布尔类型"
            )
            raise ValidateErrorException(error_msg)
        return suggested_after_answer

    def _validate_opening_statement(self, opening_statement: str) -> str:
        """验证开场白配置

        Args:
            opening_statement: 开场白文本

        Returns:
            str: 验证后的开场白文本

        Raises:
            ValidateErrorException: 当开场白配置错误时抛出

        """
        if (
            not isinstance(opening_statement, str)
            or len(opening_statement) > MAX_OPENING_STATEMENT_LENGTH
        ):
            error_msg = (
                f"开场白必须是字符串，且长度不能超过{MAX_OPENING_STATEMENT_LENGTH}"
            )
            raise ValidateErrorException(error_msg)
        return opening_statement

    def _validate_opening_questions(self, opening_questions: list) -> list:
        """验证开场问题配置

        Args:
            opening_questions: 开场问题列表

        Returns:
            list: 验证后的开场问题列表

        Raises:
            ValidateErrorException: 当开场问题配置错误时抛出

        """
        if (
            not isinstance(opening_questions, list)
            or len(opening_questions) > MAX_OPENING_QUESTIONS_COUNT
        ):
            error_msg = (
                f"开场白问题必须是列表，且个数不能超过{MAX_OPENING_QUESTIONS_COUNT}"
            )
            raise ValidateErrorException(error_msg)
        for question in opening_questions:
            if not isinstance(question, str):
                error_msg = "开场白问题必须是字符串"
                raise ValidateErrorException(error_msg)
        return opening_questions

    def _validate_speech_to_text(self, speech_to_text: dict) -> dict:
        """验证语音转文本配置

        Args:
            speech_to_text: 语音转文本配置字典

        Returns:
            dict: 验证后的语音转文本配置

        Raises:
            ValidateErrorException: 当语音转文本配置错误时抛出

        """
        if not speech_to_text or not isinstance(speech_to_text, dict):
            error_msg = "语音转文本配置必须是字典"
            raise ValidateErrorException(error_msg)
        if set(speech_to_text.keys()) != {"enable"} or not isinstance(
            speech_to_text["enable"],
            bool,
        ):
            error_msg = (
                "语音转文本配置必须是包含enable键的字典，且enable的值必须是布尔类型"
            )
            raise ValidateErrorException(error_msg)
        return speech_to_text

    def _validate_text_to_speech(self, text_to_speech: dict) -> dict:
        """验证文本转语音配置

        Args:
            text_to_speech: 文本转语音配置字典

        Returns:
            dict: 验证后的文本转语音配置

        Raises:
            ValidateErrorException: 当文本转语音配置错误时抛出

        """
        if not text_to_speech or not isinstance(text_to_speech, dict):
            error_msg = "文本转语音配置必须是字典"
            raise ValidateErrorException(error_msg)
        if (
            set(text_to_speech.keys())
            != {
                "enable",
                "voice",
                "auto_play",
            }
            or not isinstance(text_to_speech["enable"], bool)
            # TODO: voice类型需要进一步确认
            or not isinstance(
                text_to_speech["voice"],
                str,
            )
            or not isinstance(text_to_speech["auto_play"], bool)
        ):
            error_msg = (
                "文本转语音配置必须是包含enable、voice、auto_play键的字典，且enable的值必须是布尔类型，"
                "voice的值必须是字符串，auto_play的值必须是布尔类型"
            )
            raise ValidateErrorException(error_msg)
        return text_to_speech

    def _validate_review_config(self, review_config: dict) -> dict:
        """验证审核配置

        Args:
            review_config: 审核配置字典

        Returns:
            dict: 验证后的审核配置

        Raises:
            ValidateErrorException: 当审核配置错误时抛出

        """
        if not review_config or not isinstance(review_config, dict):
            error_msg = "审核配置必须是字典"
            raise ValidateErrorException(error_msg)
        if set(review_config.keys()) != {
            "enable",
            "keywords",
            "inputs_config",
            "outputs_config",
        }:
            error_msg = (
                "审核配置必须是包含enable、keywords、inputs_config、"
                "outputs_config键的字典"
            )
            raise ValidateErrorException(error_msg)
        if (
            not isinstance(review_config["keywords"], list)
            or (review_config["enable"] and len(review_config["keywords"]) == 0)
            or len(review_config["keywords"]) > MAX_REVIEW_KEYWORDS_COUNT
        ):
            error_msg = f"keywords必须是长度为1-{MAX_REVIEW_KEYWORDS_COUNT}的列表"
            raise ValidateErrorException(error_msg)
        for keyword in review_config["keywords"]:
            if not isinstance(keyword, str):
                error_msg = "keywords必须是字符串"
                raise ValidateErrorException(error_msg)
        if not review_config["inputs_config"] or not isinstance(
            review_config["inputs_config"],
            dict,
        ):
            error_msg = "inputs_config必须是字典"
            raise ValidateErrorException(error_msg)
        if (
            set(review_config["inputs_config"].keys())
            != {
                "enable",
                "preset_response",
            }
            or not isinstance(review_config["inputs_config"]["enable"], bool)
            or not isinstance(
                review_config["inputs_config"]["preset_response"],
                str,
            )
        ):
            error_msg = (
                "inputs_config必须是包含enable、preset_response键的字典, "
                "enable必须是布尔值，preset_response必须是字符串"
            )
            raise ValidateErrorException(error_msg)
        if not review_config["outputs_config"] or not isinstance(
            review_config["outputs_config"],
            dict,
        ):
            error_msg = "outputs_config必须是字典"
            raise ValidateErrorException(error_msg)
        if set(review_config["outputs_config"].keys()) != {
            "enable",
        } or not isinstance(review_config["outputs_config"]["enable"], bool):
            error_msg = "outputs_config必须是包含enable键的字典, 且enable必须是布尔值"
            raise ValidateErrorException(error_msg)
        if (
            review_config["enable"]
            and review_config["inputs_config"]["enable"] is False
            and review_config["outputs_config"]["enable"] is False
        ):
            error_msg = "enable为True时，inputs_config和outputs_config至少有一个为True"
            raise ValidateErrorException(error_msg)
        if (
            review_config["enable"]
            and review_config["inputs_config"]["enable"]
            and review_config["inputs_config"]["preset_response"].strip() == ""
        ):
            error_msg = "preset_response不能为空"
            raise ValidateErrorException(error_msg)
        return review_config

    def _validate_draft_app_config(  # noqa: PLR0912
        self,
        draft_app_config: dict[str, Any],
        account: Account,
    ) -> dict:
        """验证草稿应用配置

        Args:
            draft_app_config: 草稿应用配置字典
            account: 用户账户信息

        Returns:
            dict: 验证后的草稿应用配置

        Raises:
            ValidateErrorException: 当草稿配置格式错误时抛出

        """
        # 定义允许的配置字段列表
        acceptable_fields = [
            "model_config",  # 模型配置
            "dialog_round",  # 对话轮次配置
            "preset_prompt",  # 预设提示词
            "tools",  # 工具配置
            "workflows",  # 工作流配置
            "datasets",  # 知识库配置
            "retrieval_config",  # 检索配置
            "long_term_memory",  # 长期记忆配置
            "opening_statement",  # 开场白
            "opening_questions",  # 开场问题
            "suggested_after_answer",  # 对话后生成的建议问题
            "speech_to_text",  # 语音转文字配置
            "text_to_speech",  # 文字转语音配置
            "review_config",  # 审核配置
        ]

        # 验证配置格式：
        # 1. 配置不能为空
        # 2. 配置必须是字典类型
        # 3. 配置中的所有字段都必须在允许的字段列表中
        if (
            not draft_app_config
            or not isinstance(draft_app_config, dict)
            or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            error_msg = "草稿配置格式错误"
            raise ValidateErrorException(error_msg)

        # 验证模型配置
        if "model_config" in draft_app_config:
            draft_app_config["model_config"] = self._validate_model_config(
                draft_app_config["model_config"],
            )

        # 验证对话轮次配置
        if "dialog_round" in draft_app_config:
            draft_app_config["dialog_round"] = self._validate_dialog_round(
                draft_app_config["dialog_round"],
            )

        # 验证预设提示词
        if "preset_prompt" in draft_app_config:
            draft_app_config["preset_prompt"] = self._validate_preset_prompt(
                draft_app_config["preset_prompt"],
            )

        # 验证工具配置
        if "tools" in draft_app_config:
            draft_app_config["tools"] = self._validate_tools(
                draft_app_config["tools"],
                account,
            )

        # 验证工作流配置
        if "workflows" in draft_app_config:
            draft_app_config["workflows"] = self._validate_workflows(
                draft_app_config["workflows"],
            )

        # 验证知识库配置
        if "datasets" in draft_app_config:
            draft_app_config["datasets"] = self._validate_datasets(
                draft_app_config["datasets"],
                account,
            )

        # 验证检索配置
        if "retrieval_config" in draft_app_config:
            draft_app_config["retrieval_config"] = self._validate_retrieval_config(
                draft_app_config["retrieval_config"],
            )

        # 验证长期记忆配置
        if "long_term_memory" in draft_app_config:
            draft_app_config["long_term_memory"] = self._validate_long_term_memory(
                draft_app_config["long_term_memory"],
            )

        # 验证开场白
        if "opening_statement" in draft_app_config:
            draft_app_config["opening_statement"] = self._validate_opening_statement(
                draft_app_config["opening_statement"],
            )

        # 验证开场问题
        if "opening_questions" in draft_app_config:
            draft_app_config["opening_questions"] = self._validate_opening_questions(
                draft_app_config["opening_questions"],
            )

        # 验证对话生成建议问题配置
        if "suggested_after_answer" in draft_app_config:
            draft_app_config["suggested_after_answer"] = (
                self._validate_suggested_after_answer(
                    draft_app_config["suggested_after_answer"],
                )
            )

        # 验证语音转文字配置
        if "speech_to_text" in draft_app_config:
            draft_app_config["speech_to_text"] = self._validate_speech_to_text(
                draft_app_config["speech_to_text"],
            )

        # 验证文字转语音配置
        if "text_to_speech" in draft_app_config:
            draft_app_config["text_to_speech"] = self._validate_text_to_speech(
                draft_app_config["text_to_speech"],
            )

        # 验证审核配置
        if "review_config" in draft_app_config:
            draft_app_config["review_config"] = self._validate_review_config(
                draft_app_config["review_config"],
            )

        # 返回验证后的配置
        return draft_app_config
