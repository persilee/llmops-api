import json
from collections.abc import Generator
from dataclasses import dataclass
from threading import Thread

from flask import current_app
from injector import inject
from langchain.messages import HumanMessage
from langchain_community.tools import Tool
from langchain_openai import ChatOpenAI

from pkg.response.response import Response
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.agent.agents.function_call_agent import FunctionCallAgent
from src.core.agent.agents.react_agent import ReACTAgent
from src.core.agent.entities.agent_entity import AgentConfig
from src.core.agent.entities.queue_entity import AgentThought, QueueEvent
from src.core.llm_model.entities.model_entity import BaseLanguageModel, ModelFeature
from src.core.memory.token_buffer_memory import TokenBufferMemory
from src.entity.app_entity import AppStatus
from src.entity.conversation_entity import InvokeFrom, MessageStatus
from src.entity.dataset_entity import RetrievalSource
from src.exception.exception import ForbiddenException, NotFoundException
from src.model.account import Account
from src.model.app import App
from src.model.conversation import Conversation, Message
from src.model.end_user import EndUser
from src.schemas.openapi_schema import OpenAPIChatReq
from src.service.app_config_service import AppConfigService
from src.service.app_service import AppService
from src.service.base_service import BaseService
from src.service.conversation_service import AgentThoughtConfig, ConversationService
from src.service.llm_model_service import LLMModelService
from src.service.retrieval_service import RetrievalConfig, RetrievalService


@dataclass
class OpenAPIServiceConfig:
    agent: FunctionCallAgent
    agent_state: dict
    conversation: Conversation
    message: Message
    app_config: dict
    account: Account


@inject
@dataclass
class OpenAPIService(BaseService):
    """OpenAPI聊天服务类

    该类负责处理OpenAPI接口的聊天请求，提供完整的对话流程管理功能。
    主要功能包括：
    - 应用验证和配置管理
    - 用户和会话的创建与管理
    - 消息记录的创建和维护
    - 语言模型(LLM)和工具的配置
    - 智能体的创建和状态管理
    - 流式和非流式响应的处理

    Attributes:
        db: SQLAlchemy数据库会话
        app_config_service: 应用配置服务
        app_service: 应用服务
        retrieval_service: 检索服务
        conversation_service: 会话服务

    """

    db: SQLAlchemy
    app_config_service: AppConfigService
    app_service: AppService
    retrieval_service: RetrievalService
    conversation_service: ConversationService
    llm_model_service: LLMModelService

    def chat(self, req: OpenAPIChatReq, account: Account) -> Generator | Response:
        """处理聊天请求的主方法

        该方法负责处理完整的聊天请求流程，包括：
        - 1.验证应用和获取配置
        - 2.获取或创建用户和会话
        - 3.创建消息记录
        - 4.配置语言模型(LLM)和工具
        - 5.配置智能体
        - 6.根据请求类型执行流式或非流式响应

        Args:
            req (OpenAPIChatReq): 聊天请求对象，包含消息内容、流式请求标志等
            account (Account): 用户账户信息，包含租户ID等认证信息

        Returns:
            Generator | Response: 根据请求类型返回生成器（流式响应）
            或响应对象（非流式响应）

        """
        # 1. 验证应用并获取配置
        # 检查应用是否存在、是否已发布，并获取应用的配置信息
        app, app_config = self._validate_and_get_app(req, account)

        # 2. 获取或创建用户和会话
        # 根据请求中的用户ID获取现有用户，或创建新用户
        # 然后基于用户ID获取或创建会话
        end_user = self._get_or_create_end_user(req, account, app)
        conversation = self._get_or_create_conversation(req, app, end_user)

        # 3. 创建消息记录
        # 在数据库中创建用户输入的消息记录，用于后续追踪和上下文管理
        message = self._create_message(req, app, conversation, end_user)

        # 4. 配置语言模型(LLM)和工具
        # 根据应用配置初始化语言模型实例
        # 配置并初始化智能体可用的工具列表（如知识库检索等）
        llm = self._configure_llm(app_config)
        tools = self._configure_tools(app_config, account)

        # 5. 配置智能体
        # 创建智能体实例并初始化其状态，包括记忆和上下文
        agent, agent_state = self._configure_agent(
            req,
            app_config,
            llm,
            tools,
            conversation,
        )

        # 6. 执行智能体并返回结果
        # 根据请求中的stream标志决定使用流式响应还是非流式响应
        # 流式响应：实时返回智能体的思考过程和回答
        # 非流式响应：等待完整回答后一次性返回结果
        if req.stream.data:
            return self._handle_streaming_response(
                OpenAPIServiceConfig(
                    agent=agent,
                    agent_state=agent_state,
                    conversation=conversation,
                    message=message,
                    app_config=app_config,
                    account=account,
                ),
            )
        return self._handle_non_streaming_response(
            OpenAPIServiceConfig(
                agent=agent,
                agent_state=agent_state,
                conversation=conversation,
                message=message,
                app_config=app_config,
                account=account,
            ),
        )

    def _validate_and_get_app(
        self,
        req: OpenAPIChatReq,
        account: Account,
    ) -> tuple[App, dict]:
        """验证应用并获取配置

        Args:
            req: OpenAPI聊天请求对象，包含应用ID等信息
            account: 账户对象，包含用户和租户信息

        Returns:
            tuple[App, dict]: 返回应用对象和配置字典

        Raises:
            NotFoundException: 当应用未发布时抛出异常

        """
        # 根据请求中的应用ID和账户信息获取应用
        app = self.app_service.get_app(req.app_id.data, account)

        # 检查应用状态是否为已发布
        # 只有已发布的应用才能进行对话
        if app.status != AppStatus.PUBLISHED:
            error_msg = "该应用未发布，请先发布应用"
            raise NotFoundException(error_msg)

        # 获取应用的配置信息
        # 配置信息包含模型参数、工具设置等
        app_config = self.app_config_service.get_app_config(app)
        return app, app_config

    def _get_or_create_end_user(
        self,
        req: OpenAPIChatReq,
        account: Account,
        app: App,
    ) -> EndUser:
        """获取或创建终端用户

        根据请求中的用户ID查找已存在的用户，如果不存在则创建新的终端用户。
        如果提供了用户ID但找不到对应的用户或用户不属于当前应用，则抛出异常。

        Args:
            req: OpenAPI聊天请求对象，包含用户ID等信息
            account: 账户对象，包含租户ID等信息
            app: 应用对象，包含应用ID等信息

        Returns:
            EndUser: 终端用户对象，可能是已存在的用户或新创建的用户

        Raises:
            ForbiddenException: 当用户不存在或不属于当前应用时抛出

        """
        # 如果请求中包含用户ID，则尝试获取现有用户
        if req.end_user_id.data:
            # 根据用户ID查询用户
            end_user = self.get(EndUser, req.end_user_id.data)
            # 检查用户是否存在且属于当前应用
            if not end_user or end_user.app_id != app.id:
                # 用户不存在或不属于当前应用时抛出异常
                error_msg = "用户不存在或不属于该应用"
                raise ForbiddenException(error_msg)
            return end_user

        # 如果没有提供用户ID，则创建新的终端用户
        # 使用账户的租户ID和应用ID创建新用户
        return self.create(EndUser, tenant_id=account.id, app_id=app.id)

    def _get_or_create_conversation(
        self,
        req: OpenAPIChatReq,
        app: App,
        end_user: EndUser,
    ) -> Conversation:
        """获取或创建会话

        Args:
            req: 包含会话ID的请求对象
            app: 当前应用对象
            end_user: 当前用户对象

        Returns:
            Conversation: 获取或创建的会话对象

        Raises:
            ForbiddenException: 当会话不存在或不属于当前应用时抛出

        """
        # 如果请求中包含会话ID，则尝试获取现有会话
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            # 验证会话是否存在且属于当前应用
            if (
                not conversation
                or conversation.app_id != app.id
                or conversation.invoke_from != InvokeFrom.SERVICE_API
                or conversation.created_by != end_user.id
            ):
                error_msg = "会话不存在或不属于该应用"
                raise ForbiddenException(error_msg)
            return conversation

        # 如果没有提供会话ID，则创建新会话
        return self.create(
            Conversation,
            app_id=app.id,  # 关联到当前应用
            name="New Conversation",  # 默认会话名称
            invoke_from=InvokeFrom.SERVICE_API,  # 标记为服务API调用创建
            created_by=end_user.id,  # 设置创建者
        )

    def _create_message(
        self,
        req: OpenAPIChatReq,
        app: App,
        conversation: Conversation,
        end_user: EndUser,
    ) -> Message:
        """创建并返回新的消息记录

        该方法用于在对话中创建一条新的消息记录，将用户输入保存到数据库中。
        消息记录包含应用ID、会话ID、调用来源、创建者、查询内容和状态等信息。

        Args:
            req (OpenAPIChatReq): 包含用户输入数据的请求对象，从中提取查询内容
            app (App): 应用对象，用于获取应用ID
            conversation (Conversation): 对话对象，用于获取会话ID
            end_user (EndUser): 结束用户对象，用于获取用户ID作为创建者

        Returns:
            Message: 创建的消息记录对象，包含所有消息相关信息

        Note:
            - 消息状态默认设置为 NORMAL
            - 调用来源固定设置为 SERVICE_API
            - 查询内容从 req.query.data 中获取

        """
        return self.create(
            Message,
            app_id=app.id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.SERVICE_API,
            created_by=end_user.id,
            query=req.query.data,
            status=MessageStatus.NORMAL,
        )

    def _configure_llm(self, app_config: dict) -> BaseLanguageModel:
        """配置并初始化ChatOpenAI模型实例

        根据应用配置中的模型参数创建并返回一个ChatOpenAI实例。
        该实例将用于后续的对话处理和智能体交互。

        Args:
            app_config (dict): 应用配置字典，包含模型配置信息
                - model_config: 模型配置部分
                    - model: 使用的模型名称（如gpt-3.5-turbo等）
                    - parameters: 模型参数配置字典，包含温度、top_p等参数

        Returns:
            ChatOpenAI: 配置好的ChatOpenAI模型实例，可用于对话生成

        Note:
            - model_config["parameters"]中的参数将直接传递给ChatOpenAI构造函数
            - 具体支持的参数请参考ChatOpenAI官方文档

        """
        return self.llm_model_service.load_language_model(
            app_config.get("model_config", {}),
        )

    def _configure_tools(self, app_config: dict, account: Account) -> list[Tool]:
        """配置工具列表

        Args:
            app_config (dict): 应用配置字典，包含工具和知识库等配置信息
            account (Account): 用户账户信息，用于权限验证和资源访问

        Returns:
            list[Tool]: 配置好的工具列表，包括基础工具和检索工具（如果配置了知识库）

        """
        # 从应用配置中获取LangChain工具列表
        # app_config["tools"] 包含了工具的配置信息
        tools = self.app_config_service.get_langchain_tools_by_config(
            app_config["tools"],
        )

        # 检查是否配置了知识库
        # 如果配置了知识库，则创建检索工具并添加到工具列表中
        # 检索工具允许智能体能够查询和利用知识库中的信息
        if app_config["datasets"]:
            retrieval_tool = self._create_retrieval_tool(app_config, account)
            tools.append(retrieval_tool)

        # 返回配置完成的工具列表
        return tools

    def _create_retrieval_tool(self, app_config: dict, account: Account) -> Tool:
        """创建用于知识库检索的LangChain工具。

        该方法根据应用配置和账户信息创建一个检索工具，该工具可以被智能体调用进行知识库检索。
        它会从应用配置中提取知识库ID和检索参数，构建检索配置对象，然后使用检索服务创建LangChain工具。

        Args:
            app_config (dict): 应用配置字典，包含知识库信息和检索配置
                - datasets: 知识库列表，每个知识库包含id字段
                - retrieval_config: 检索相关配置参数
            account (Account): 账户对象，包含账户ID等信息

        Returns:
            Tool: 可被智能体调用的LangChain检索工具

        Raises:
            KeyError: 当app_config中缺少必要的配置项时

        """
        # 创建检索配置对象，配置知识库检索的相关参数
        retrieval_config = RetrievalConfig(
            flask_app=current_app._get_current_object(),  # noqa: SLF001
            dataset_ids=[
                dataset["id"] for dataset in app_config["datasets"]
            ],  # 从应用配置中提取所有知识库ID
            account_id=account.id,  # 设置当前操作的账户ID
            retrieval_source=RetrievalSource.APP,  # 指定检索来源为应用配置的知识库
            **app_config["retrieval_config"],  # 展开应用配置中的检索相关配置参数
        )

        # 使用检索服务创建LangChain工具，该工具可以被智能体调用进行知识检索
        return self.retrieval_service.create_langchain_tool_from_search(
            retrieval_config,
        )

    def _configure_agent(
        self,
        req: OpenAPIChatReq,
        app_config: dict,
        llm: ChatOpenAI,
        tools: list[Tool],
        conversation: Conversation,
    ) -> tuple[FunctionCallAgent, dict]:
        """配置智能体和智能体状态

        Args:
            req: OpenAPI聊天请求对象，包含用户输入的查询内容
            app_config: 应用配置字典，包含对话轮次、长期记忆等配置
            llm: ChatOpenAI模型实例，用于生成回复
            tools: 可用工具列表，供智能体调用
            conversation: 对话对象，包含对话历史和摘要信息

        Returns:
            tuple: (FunctionCallAgent实例, 智能体状态字典)

        """
        # 创建令牌缓冲记忆，用于管理对话历史和上下文
        # db: 数据库会话，用于持久化对话历史
        # conversation: 当前对话对象，包含对话ID和相关信息
        # model_instance: 语言模型实例，用于计算token数量
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )

        # 获取历史对话记录，限制对话轮数以控制上下文长度
        # message_limit: 最大保留的消息轮数，从app_config中获取
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

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
            agent_config=AgentConfig(
                user_id=req.app_id.data,  # 用户ID，用于标识对话发起者
                invoke_from=InvokeFrom.DEBUGGER,  # 调用来源，标识场景类型
                preset_prompt=app_config["preset_prompt"],  # 预设提示，用于引导对话
                enable_long_term_memory=app_config["long_term_memory"][
                    "enable"
                ],  # 是否启用长期记忆
                tools=tools,  # 可用工具列表
                review_config=app_config["review_config"],  # 审核配置
            ),
        )

        # 准备智能体状态信息，包含当前消息、历史记录和长期记忆
        # messages: 当前用户输入的消息列表
        # history: 历史对话消息列表，用于保持上下文连续性
        # long_term_memory: 对话摘要，用于长期记忆存储
        agent_state = {
            "messages": [
                HumanMessage(req.query.data),
            ],  # 将用户查询转换为HumanMessage对象
            "history": history,  # 获取的历史对话记录
            "long_term_memory": conversation.summary,  # 对话的长期记忆摘要
        }

        return agent, agent_state

    def _handle_streaming_response(self, config: OpenAPIServiceConfig) -> Generator:
        """处理流式响应的方法

        该方法用于处理智能体的流式输出，通过生成器实时返回智能体的思考过程。
        它会遍历智能体的流式输出，为每个思考记录生成事件ID，并更新思考记录字典。
        同时，它会生成并返回SSE格式的事件，用于向客户端推送实时数据。
        最后，在流式处理完成后，异步保存所有智能体思考记录。

        Args:
            config (OpenAPIServiceConfig): 包含处理流式响应所需的所有配置信息，
                包括智能体、会话、消息、应用配置和账户信息等

        Returns:
            Generator: 返回一个生成器对象，用于流式输出智能体的思考过程

        """
        # 初始化智能体思考记录字典，用于存储流式处理过程中的思考记录
        agent_thoughts_dict = {}

        def handle_stream() -> Generator:
            """内部生成器函数，用于处理流式输出的每个思考记录

            遍历智能体的流式输出，为每个思考记录生成事件ID，
            更新思考记录字典，并生成SSE格式的事件。

            Yields:
                str: SSE格式的事件字符串，包含智能体的思考记录

            """
            # 遍历智能体的流式输出，每个元素是一个AgentThought对象
            for agent_thought in config.agent.stream(config.agent_state):
                # 生成事件ID，用于标识和关联思考记录
                event_id = str(agent_thought.id)

                # 如果不是心跳事件，则更新智能体思考记录字典
                if agent_thought.event != QueueEvent.PING:
                    self._update_agent_thoughts(
                        agent_thoughts_dict,
                        agent_thought,
                        event_id,
                    )

                # 生成并返回SSE（Server-Sent Events）格式的事件
                # SSE用于服务器向客户端推送实时数据
                yield self._generate_sse_event(
                    agent_thought,
                    event_id,
                    config.conversation,
                    config.message,
                )

            # 流式处理完成后，异步保存所有智能体思考记录
            # 使用异步保存可以避免阻塞主流程，提高响应速度
            self._save_agent_thoughts_async(
                agent_thoughts_dict,
                config.conversation,
                config.message,
                config.app_config,
                config.account,
            )

        # 返回生成器对象，用于流式输出
        return handle_stream()

    def _handle_non_streaming_response(self, config: OpenAPIServiceConfig) -> Response:
        """处理非流式响应"""
        # 调用智能体处理请求，传入当前智能体状态
        # agent.invoke() 会执行智能体的主要逻辑，包括思考过程和最终回答
        agent_result = config.agent.invoke(config.agent_state)

        # 异步保存智能体思考记录，避免阻塞主流程
        # 使用异步保存是因为思考记录的保存不需要等待响应完成
        # 这样可以提高响应速度，提升用户体验
        self._save_agent_thoughts_async(
            agent_result.agent_thoughts,  # 智能体的完整思考过程
            config.conversation,  # 对话上下文
            config.message,  # 当前消息
            config.app_config,  # 应用配置
            config.account,  # 账户信息
        )

        # 构建并返回响应数据
        return Response(
            data={
                "id": str(config.message.id),  # 消息ID
                "end_user_id": str(config.conversation.created_by),  # 发起对话的用户ID
                "conversation_id": str(config.conversation.id),  # 对话ID
                "query": config.message.query,  # 用户输入的查询内容
                "answer": agent_result.answer,  # 智能体的回答内容
                "total_token_count": 0,  # 总token计数（当前固定为0）
                "latency": agent_result.latency,  # 响应延迟时间
                "agent_thoughts": self._format_agent_thoughts(  # 格式化后的思考过程
                    agent_result.agent_thoughts,
                ),
            },
        )

    def _update_agent_thoughts(
        self,
        agent_thoughts_dict: dict,  # 存储智能体思考记录的字典
        agent_thought: AgentThought,  # 新的智能体思考记录
        event_id: str,  # 事件ID，用于标识和关联思考记录
    ) -> None:
        """更新智能体思考记录

        根据事件类型更新智能体思考记录：
        - 对于消息事件（AGENT_MESSAGE），合并思考过程和答案
        - 对于其他事件，直接存储新的思考记录

        Args:
            agent_thoughts_dict: 存储智能体思考记录的字典，key为event_id
            agent_thought: 新的智能体思考记录对象
            event_id: 事件ID，用于标识和关联思考记录

        """
        # 处理消息事件
        if agent_thought.event == QueueEvent.AGENT_MESSAGE:
            # 如果事件ID不存在于字典中，直接添加新记录
            if event_id not in agent_thoughts_dict:
                agent_thoughts_dict[event_id] = agent_thought
            else:
                # 如果事件已存在，合并思考过程和答案
                # 使用model_copy创建新对象，并更新以下字段：
                # - thought: 合并原有的思考过程和新的思考过程
                # - answer: 合并原有的答案和新的答案
                # - latency: 使用新的延迟时间
                agent_thoughts_dict[event_id] = agent_thoughts_dict[
                    event_id
                ].model_copy(
                    update={
                        "thought": agent_thoughts_dict[event_id].thought
                        + agent_thought.thought,  # 合并思考过程
                        "answer": agent_thoughts_dict[event_id].answer
                        + agent_thought.answer,  # 合并答案内容
                        "latency": agent_thought.latency,  # 更新延迟时间
                    },
                )
        else:
            # 对于非消息事件，直接存储新的思考记录
            agent_thoughts_dict[event_id] = agent_thought

    def _generate_sse_event(
        self,
        agent_thought: AgentThought,
        event_id: str,
        conversation: Conversation,
        message: Message,
    ) -> tuple[str, str]:
        """生成SSE事件

        Args:
            agent_thought: 智能体思考记录对象，包含事件类型、思考内容、观察结果等信息
            event_id: 事件的唯一标识符
            conversation: 会话对象，用于获取会话ID
            message: 消息对象，用于获取消息ID

        Returns:
            tuple[str, str]: 返回SSE格式的字符串，包含事件类型和数据

        """
        # 构建事件数据字典，包含智能体思考记录的指定字段和额外信息
        data = {
            # 从agent_thought中提取指定字段：
            # 事件类型、思考内容、观察结果、工具信息、工具输入、答案和延迟
            **agent_thought.model_dump(
                include={
                    "event",
                    "thought",
                    "observation",
                    "tool",
                    "tool_input",
                    "answer",
                    "latency",
                },
            ),
            # 添加事件唯一标识符
            "id": event_id,
            # 添加会话ID（转换为字符串格式）
            "conversation_id": str(conversation.id),
            # 添加消息ID（转换为字符串格式）
            "message_id": str(message.id),
            # 添加任务ID（转换为字符串格式）
            "task_id": str(agent_thought.task_id),
        }

        # 返回SSE格式的事件字符串，格式为：event: 事件类型\ndata: JSON数据\n\n
        return f"event: {agent_thought.event.value}\ndata:{json.dumps(data)}\n\n"

    def _save_agent_thoughts_async(
        self,
        agent_thoughts: list[AgentThought] | dict,
        conversation: Conversation,
        message: Message,
        app_config: dict,
        account: Account,
    ) -> None:
        """异步保存智能体思考记录

        该方法通过创建一个新的线程来异步保存智能体的思考记录，避免阻塞主线程。
        它会将智能体的思考过程持久化到数据库中，以便后续分析和查看。

        Args:
            agent_thoughts: 智能体思考记录列表或字典形式的思考记录
                如果是字典类型，会将其转换为列表形式
            conversation: 对话实体，包含对话的基本信息
            message: 消息实体，包含消息的基本信息
            app_config: 应用配置字典，包含应用的各项配置信息
            account: 账户实体，包含用户的基本信息

        Returns:
            None

        Note:
            该方法使用线程来实现异步保存，不会阻塞调用方法的线程

        """
        # 创建智能体思考配置对象，包含保存思考记录所需的所有配置信息
        agent_thought_config = AgentThoughtConfig(
            flask_app=current_app._get_current_object(),  # noqa: SLF001
            account_id=account.id,
            app_id=conversation.app_id,
            app_config=app_config,
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=list(agent_thoughts.values())
            if isinstance(agent_thoughts, dict)
            else agent_thoughts,
        )

        # 创建并启动新线程来执行保存操作
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={"config": agent_thought_config},
        )
        thread.start()

    def _format_agent_thoughts(self, agent_thoughts: list[AgentThought]) -> list[dict]:
        """格式化智能体思考记录列表为字典列表

        将 AgentThought 对象列表转换为包含特定字段的字典列表，用于 API 响应。
        每个字典包含智能体思考的各个关键信息。
        401
        Args:
            agent_thoughts: AgentThought 对象列表，包含智能体的思考记录

        Returns:
            list[dict]: 格式化后的思考记录列表，每个字典包含以下字段：
                - id: 思考记录的唯一标识符
                - event: 事件类型
                - thought: 智能体的思考内容
                - observation: 观察结果
                - tool: 使用的工具名称
                - latency: 响应延迟时间
                - tool_input: 工具输入参数
                - created_at: 创建时间戳（当前固定为0）

        """
        return [
            {
                "id": str(agent_thought.id),
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "latency": agent_thought.latency,
                "tool_input": agent_thought.tool_input,
                "created_at": 0,
            }
            for agent_thought in agent_thoughts
        ]
