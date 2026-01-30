import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from flask import Flask
from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
)
from langchain_openai import ChatOpenAI
from redis import Redis, RedisError
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from src.core.agent.entities.queue_entity import QueueEvent
from src.entity.conversation_entity import (
    CONVERSATION_NAME_TEMPLATE,
    MAX_CONVERSATION_NAME_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_SUGGESTED_QUESTIONS,
    SUGGESTED_QUESTIONS_TEMPLATE,
    SUMMARIZER_TEMPLATE,
    TRUNCATE_PREFIX_LENGTH,
    ConversationInfo,
    InvokeFrom,
    MessageStatus,
    SuggestedQuestions,
)
from src.exception.exception import NotFoundException
from src.model.account import Account
from src.model.conversation import Conversation, Message, MessageAgentThought
from src.schemas.app_schema import (
    GenerateShareConversationReq,
    GetDebugConversationMessagesWithPageResp,
)
from src.schemas.conversation_schema import GetConversationMessagesWithPageReq
from src.service.base_service import BaseService

logger = logging.getLogger(__name__)


@dataclass
class AgentThoughtConfig:
    flask_app: Flask
    account_id: UUID
    app_id: UUID
    app_config: dict[str, Any]
    conversation_id: UUID
    message_id: UUID
    agent_thoughts: dict[str, Any]


@inject
@dataclass
class ConversationService(BaseService):
    db: SQLAlchemy
    redis_client: Redis

    def get_conversation_messages_with_page(
        self,
        conversation_id: UUID,
        req: GetConversationMessagesWithPageReq,
        account: Account,
    ) -> tuple[list[Message], Paginator]:
        """根据传递的会话id+请求数据，获取当前账号下该会话的消息分页列表数据"""
        # 1.获取会话并校验权限
        conversation = self.get_conversation(conversation_id, account)

        # 2.构建分页器并设置游标条件
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 3.将时间戳转换成DateTime
            created_at_datetime = datetime.fromtimestamp(
                req.created_at.data,
                tz=UTC,
            )
            filters.append(Message.created_at <= created_at_datetime)

        # 4.执行分页并查询数据
        messages = paginator.paginate(
            self.db.session.query(Message)
            .options(joinedload(Message.agent_thoughts))
            .filter(
                Message.conversation_id == conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                ~Message.is_deleted,
                *filters,
            )
            .order_by(desc("created_at")),
        )

        return messages, paginator

    def delete_conversation(
        self,
        conversation_id: UUID,
        account: Account,
    ) -> Conversation:
        """根据传递的会话id+账号删除指定的会话记录"""
        # 1.获取会话记录并校验权限
        conversation = self.get_conversation(conversation_id, account)

        # 2.更新会话的删除状态
        self.update(conversation, is_deleted=True)

        return conversation

    def get_conversation(self, conversation_id: UUID, account: Account) -> Conversation:
        """根据传递的会话id+account，获取指定的会话信息"""
        # 1.根据conversation_id查询会话记录
        conversation = self.get(Conversation, conversation_id)
        if (
            not conversation
            or conversation.created_by != account.id
            or conversation.is_deleted
        ):
            error_msg = "该会话不存在或被删除，请核实后重试"
            raise NotFoundException(error_msg)

        # 2.校验通过返回会话
        return conversation

    def delete_message(
        self,
        conversation_id: UUID,
        message_id: UUID,
        account: Account,
    ) -> Message:
        """根据传递的会话id+消息id删除指定的消息记录"""
        # 1.获取会话记录并校验权限
        conversation = self.get_conversation(conversation_id, account)

        # 2.获取消息并校验权限
        message = self.get_message(message_id, account)

        # 3.判断消息和会话是否关联
        if conversation.id != message.conversation_id:
            error_msg = "该会话下不存在该消息，请核实后重试"
            raise NotFoundException(error_msg)

        # 4.校验通过修改消息is_deleted属性标记删除
        self.update(message, is_deleted=True)

        return message

    def get_message(self, message_id: UUID, account: Account) -> Message:
        """根据传递的消息id+账号，获取指定的消息"""
        # 1.根据message_id查询消息记录
        message = self.get(Message, message_id)
        if not message or message.created_by != account.id or message.is_deleted:
            error_msg = "该消息不存在或被删除，请核实后重试"
            raise NotFoundException(error_msg)

        # 2.校验通过返回消息
        return message

    def update_conversation(
        self,
        conversation_id: UUID,
        account: Account,
        **kwargs: dict,
    ) -> Conversation:
        """根据传递的会话id+账号+kwargs更新会话信息"""
        # 1.获取会话记录并校验权限
        conversation = self.get_conversation(conversation_id, account)

        # 2.更新会话信息
        self.update(conversation, **kwargs)

        return conversation

    def get_share_conversation(self, share_id: str) -> list[Message] | None:
        """从Redis缓存中获取分享的对话内容

        Args:
            share_id: 分享对话的唯一标识符

        Returns:
            list[Message] | None: 如果找到则返回消息列表，否则返回None

        """
        try:
            # 检查缓存中是否存在该分享ID
            if self.redis_client.exists(share_id):
                # 从Redis获取缓存的JSON格式消息数据
                messages_json = self.redis_client.get(share_id)

                # 将JSON数据反序列化为消息列表并返回
                return json.loads(messages_json)
        except (RedisError, json.JSONDecodeError):
            # 如果发生Redis错误或JSON解析错误，静默处理并返回None
            pass

        # 如果缓存中不存在或发生错误，返回None
        return None

    def generate_share_conversation(
        self,
        req: GenerateShareConversationReq,
    ) -> str:
        """生成分享对话的缓存键并存储对话消息。

        该方法会生成一个基于当前UTC时间的缓存键，用于标识分享的对话。
        首先尝试从Redis缓存中获取已存在的对话消息，如果不存在则从数据库查询。
        查询到的消息会被序列化并存储到Redis缓存中，缓存有效期为72小时。

        Args:
            req (GenerateShareConversationReq): 生成分享对话的请求对象，
            包含对话ID和消息ID列表

        Returns:
            str: 返回生成的缓存键作为分享ID，格式为"年_月_日_时_分_秒:对话ID"

        Raises:
            RedisError: 当Redis操作失败时会被捕获并继续执行数据库查询
            json.JSONDecodeError: 当JSON解析失败时会被捕获并继续执行数据库查询

        """
        # 生成基于当前UTC时间的缓存键，格式为：年_月_日_时_分_秒:对话ID
        current_time = datetime.now(UTC).strftime("%Y_%m_%d_%H_%M_%S")
        cache_key = f"{current_time}:{req.conversation_id.data!s}"

        try:
            # 尝试从Redis缓存中获取已存在的对话消息
            if self.redis_client.exists(cache_key):
                messages = self.redis_client.get(cache_key)
                # 如果缓存存在，直接返回解析后的JSON数据
                return json.loads(messages)
        except (RedisError, json.JSONDecodeError):
            # 如果Redis操作失败或JSON解析失败，继续执行数据库查询
            pass

        # 从数据库查询指定的对话消息
        # 根据对话ID和消息ID列表进行过滤，并按创建时间倒序排列
        messages = (
            self.db.session.query(Message)
            .filter(
                Message.conversation_id == req.conversation_id.data,
                Message.id.in_(req.message_ids.data),
            )
            .order_by(desc("created_at"))
            .all()
        )

        # 创建响应对象，用于序列化消息数据
        resp = GetDebugConversationMessagesWithPageResp(many=True)

        # 将查询结果序列化并存储到Redis缓存中
        # 设置缓存过期时间为72小时（72 * 60 * 60秒）
        # 使用自定义的default函数处理UUID类型的序列化
        self.redis_client.setex(
            cache_key,
            72 * 60 * 60,
            json.dumps(
                resp.dump(messages),
                default=lambda o: str(o) if isinstance(o, UUID) else o,
            ),
        )

        # 返回缓存键作为分享ID，用于后续访问分享的对话内容
        return cache_key

    @classmethod
    def _serialize_message(cls, msg) -> dict:
        """将消息对象转换为可序列化的字典"""
        data = msg.__dict__.copy()
        # 将所有UUID字段转换为字符串
        for key, value in data.items():
            if isinstance(value, UUID):
                data[key] = str(value)
        return data

    @classmethod
    def summary(
        cls,
        human_message: str,
        ai_message: str,
        old_summary: str = "",
    ) -> str:
        """生成对话摘要，将新的对话内容与已有摘要合并。

        Args:
            human_message (str): 用户输入的消息内容
            ai_message (str): AI生成的回复内容
            old_summary (str, optional): 已有的对话摘要，默认为空字符串

        Returns:
            str: 合并后的新摘要文本

        该方法使用GPT模型来智能地整合新的对话内容到已有摘要中，
        保持摘要的连贯性和关键信息的完整性。

        """
        # 创建一个聊天提示模板，使用预定义的SUMMARIZER_TEMPLATE
        prompt = ChatPromptTemplate.from_template(SUMMARIZER_TEMPLATE)

        # 初始化一个ChatOpenAI模型实例，使用"gpt-4o-mini"模型，设置温度为0.5
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

        # 创建一个处理链，将提示模板、语言模型和字符串输出解析器连接在一起
        summary_chain = prompt | llm | StrOutputParser()

        # 调用处理链并传入参数，返回生成的摘要
        return summary_chain.invoke(
            {
                "summary": old_summary,
                "new_lines": f"Human: {human_message}\nAI: {ai_message}",
            },
        )

    @classmethod
    def generate_conversation(cls, query: str) -> str:
        """根据用户输入生成对话名称。

        该方法使用GPT模型分析用户输入，提取对话的主题和意图，
        生成一个简洁的对话名称。支持多语言输入，并会对过长的
        输入进行智能截断处理。

        Args:
            query (str): 用户的输入文本，可能包含多语言内容

        Returns:
            str: 生成的对话名称，长度限制在MAX_CONVERSATION_NAME_LENGTH内

        处理流程：
        1. 对超长输入进行截断处理，保留开头和结尾的关键内容
        2. 使用GPT模型分析输入，提取对话主题
        3. 对生成的名称进行长度限制
        4. 返回处理后的对话名称

        异常处理：
        如果在提取对话名称过程中发生错误，会记录异常日志，
        并返回一个默认的对话名称。

        注意：
        - 输入文本超过MAX_QUERY_LENGTH会被自动截断
        - 输出名称长度会被限制在MAX_CONVERSATION_NAME_LENGTH内
        - 支持多语言输入，输出语言会与输入语言保持一致

        """
        # 创建一个聊天提示模板，包含系统消息和用户输入
        prompt = ChatPromptTemplate.from_messages(
            [("system", CONVERSATION_NAME_TEMPLATE), ("human", "{query}")],
        )

        # 初始化一个使用 gpt-4o-mini 模型的聊天 AI 实例，设置温度为 0（确定性输出）
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        # 使用 with_structured_output 方法使 LLM 输出结构化的 ConversationInfo 对象
        structured_llm = llm.with_structured_output(ConversationInfo)

        # 创建一个处理链，将提示模板和结构化的 LLM 连接起来
        chain = prompt | structured_llm

        # 如果查询长度超过最大限制，则进行截断处理
        if len(query) > MAX_QUERY_LENGTH:
            # 保留开头和结尾各 TRUNCATE_PREFIX_LENGTH 个字符，中间用省略号代替
            query = (
                query[:TRUNCATE_PREFIX_LENGTH]
                + "...[TRUNCATED]..."
                + query[-TRUNCATE_PREFIX_LENGTH:]
            )
        # 将查询中的换行符替换为空格
        query = query.replace("\n", " ")

        # 调用处理链，传入查询并获取会话信息
        conversation_info = chain.invoke({"query": query})

        name = ""
        try:
            # 尝试从会话信息中提取主题名称
            if conversation_info and hasattr(conversation_info, "subject"):
                name = conversation_info.subject
        except Exception as e:
            # 如果提取过程中发生异常，记录错误信息
            error_msg = (
                f"提取会话名称失败: {e!s}, conversation_info: {conversation_info}"
            )
            logger.exception(error_msg)

        # 如果生成的名称超过最大长度限制，进行截断处理
        if len(name) > MAX_CONVERSATION_NAME_LENGTH:
            name = name[:MAX_CONVERSATION_NAME_LENGTH] + "..."

        # 返回处理后的会话名称
        return name

    @classmethod
    def generate_suggested_questions(cls, histories: str) -> list[str]:
        """根据对话历史生成建议问题列表。

        该方法使用GPT模型分析对话历史，智能生成与上下文相关的建议问题，
        用于帮助用户继续对话或探索相关话题。

        Args:
            histories (str): 对话历史记录，包含用户和AI的交互内容

        Returns:
            list[str]: 建议问题列表，数量限制在MAX_SUGGESTED_QUESTIONS内

        处理流程：
        1. 使用预定义的SUGGESTED_QUESTIONS_TEMPLATE创建提示模板
        2. 初始化GPT-4o-mini模型，设置温度为0以确保输出的确定性
        3. 通过结构化输出配置，使模型返回标准化的建议问题格式
        4. 处理对话历史并生成建议问题
        5. 对生成的问题列表进行数量限制处理

        异常处理：
        如果在生成或提取建议问题过程中发生错误，会记录异常日志，
        并返回空列表作为默认值。

        注意：
        - 输入的对话历史会被完整传递给模型进行分析
        - 输出的问题数量会被限制在MAX_SUGGESTED_QUESTIONS以内
        - 生成的建议问题与对话历史上下文相关
        - 使用结构化输出确保返回格式的一致性

        """
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SUGGESTED_QUESTIONS_TEMPLATE),  # 系统消息模板
                ("human", "{histories}"),  # 用户输入模板
            ],
        )

        # 初始化一个使用 gpt-4o-mini 模型的聊天 AI 实例，设置温度为 0（确定性输出）
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        # 使用 with_structured_output 方法使 LLM 输出结构化的 SuggestedQuestions 对象
        structured_llm = llm.with_structured_output(SuggestedQuestions)

        # 创建一个处理链，将提示模板和结构化的 LLM 连接起来
        chain = prompt | structured_llm

        # 调用处理链，传入查询并获取建议问题列表
        suggested_questions = chain.invoke({"histories": histories})

        questions = []
        try:
            # 尝试从会话信息中提取主题名称
            if suggested_questions and hasattr(suggested_questions, "questions"):
                questions = suggested_questions.questions
        except Exception as e:
            # 如果提取过程中发生异常，记录错误信息
            error_msg = (
                f"提取会话建议问题列表失败: {e!s},",
                f" suggested_questions: {suggested_questions}",
            )
            logger.exception(error_msg)

        if len(questions) > MAX_SUGGESTED_QUESTIONS:
            questions = questions[:MAX_SUGGESTED_QUESTIONS]

        return questions

    def save_agent_thoughts(
        self,
        config: AgentThoughtConfig,
    ) -> None:
        """保存智能体的思考记录到数据库。

        该方法处理智能体的思考过程，包括：
        - 保存智能体的思考记录
        - 更新消息内容和状态
        - 生成对话摘要（如果启用长期记忆）
        - 为新对话生成名称
        - 处理终止状态（停止、错误或超时）

        Args:
            config (AgentThoughtConfig): 包含以下配置信息：
                - flask_app: Flask应用实例
                - app_id: 应用ID
                - conversation_id: 对话ID
                - message_id: 消息ID
                - account_id: 账户ID
                - agent_thoughts: 智能体思考记录列表
                - draft_app_config: 应用配置，包含长期记忆设置

        Returns:
            None

        """
        # 在Flask应用上下文中执行，确保可以访问数据库等资源
        with config.flask_app.app_context():
            # 初始化延迟时间计数器
            latency = 0

            # 获取对话和消息对象
            conversation = self.get(Conversation, config.conversation_id)
            message = self.get(Message, config.message_id)

            # 遍历智能体思考记录，position表示事件在序列中的位置
            for position, agent_thought in enumerate(config.agent_thoughts, start=1):
                # 检查事件类型是否为需要记录的类型
                if agent_thought.event in [
                    QueueEvent.LONG_TERM_MEMORY_RECALL,
                    QueueEvent.AGENT_THOUGHT,
                    QueueEvent.AGENT_MESSAGE,
                    QueueEvent.AGENT_ACTION,
                    QueueEvent.DATASET_RETRIEVAL,
                ]:
                    # 累加延迟时间
                    latency += agent_thought.latency

                    # 创建消息智能体思考记录
                    self.create(
                        MessageAgentThought,
                        app_id=config.app_id,  # 应用ID
                        conversation_id=conversation.id,  # 对话ID
                        message_id=message.id,  # 消息ID
                        invoke_from=InvokeFrom.DEBUGGER,  # 调用来源
                        created_by=config.account_id,  # 创建者ID
                        position=position,  # 事件位置
                        event=agent_thought.event,  # 事件类型
                        thought=agent_thought.thought,  # 思考内容
                        observation=agent_thought.observation,  # 观察结果
                        tool=agent_thought.tool,  # 使用的工具
                        tool_input=agent_thought.tool_input,  # 工具输入
                        message=agent_thought.message,  # 消息内容
                        message_token_count=agent_thought.message_token_count,
                        message_unit_price=agent_thought.message_unit_price,
                        message_price_unit=agent_thought.message_price_unit,
                        answer=agent_thought.answer,  # 答案内容
                        answer_token_count=agent_thought.answer_token_count,
                        answer_unit_price=agent_thought.answer_unit_price,
                        answer_price_unit=agent_thought.answer_price_unit,
                        total_token_count=agent_thought.total_token_count,
                        total_price=agent_thought.total_price,
                        latency=agent_thought.latency,  # 延迟时间
                    )

                # 如果是智能体消息事件
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    # 更新消息内容和答案
                    self.update(
                        message,
                        message=agent_thought.message,  # 消息内容
                        message_token_count=agent_thought.message_token_count,
                        message_unit_price=agent_thought.message_unit_price,
                        message_price_unit=agent_thought.message_price_unit,
                        answer=agent_thought.answer,  # 答案内容
                        answer_token_count=agent_thought.answer_token_count,
                        answer_unit_price=agent_thought.answer_unit_price,
                        answer_price_unit=agent_thought.answer_price_unit,
                        total_token_count=agent_thought.total_token_count,
                        total_price=agent_thought.total_price,
                        latency=latency,  # 总延迟时间
                    )
                    # 如果启用了长期记忆功能
                    if config.app_config["long_term_memory"]["enable"]:
                        # 生成新的对话摘要
                        new_summary = self.summary(
                            message.query,  # 查询内容
                            agent_thought.answer,  # 答案内容
                            conversation.summary,  # 当前摘要
                        )
                        self.update(
                            conversation,
                            summary=new_summary,
                        )

                    # 如果是新对话，生成新的对话名称
                    if conversation.is_new:
                        new_conversation_name = self.generate_conversation(
                            message.query,  # 基于查询内容生成名称
                        )
                        # 更新对话的名称和摘要
                        self.update(
                            conversation,
                            name=new_conversation_name,  # 新的对话名称
                        )

                # 检查代理思考的事件状态是否为终止状态（停止、错误或超时）
                if agent_thought.event in [
                    QueueEvent.STOP,  # 停止事件
                    QueueEvent.ERROR,  # 错误事件
                    QueueEvent.TIMEOUT,  # 超时事件
                ]:
                    # 更新消息状态，设置对应的事件状态和错误信息
                    self.update(
                        message,
                        status=agent_thought.event,  # 设置事件状态
                        error=agent_thought.observation,  # 设置错误信息
                    )
                    # 跳出循环，终止处理
                    break
