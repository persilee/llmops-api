import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from flask import Flask
from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

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
    SuggestedQuestions,
)
from src.model.conversation import Conversation, Message, MessageAgentThought
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
        prompt = ChatPromptTemplate.format_messages(
            [
                ("system", CONVERSATION_NAME_TEMPLATE),  # 系统消息模板
                ("human", "{query}"),  # 用户输入模板
            ],
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
                        answer=agent_thought.answer,  # 答案内容
                        latency=agent_thought.latency,  # 延迟时间
                    )

                # 如果是智能体消息事件
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    # 更新消息内容和答案
                    self.update(
                        message,
                        message=agent_thought.message,  # 消息内容
                        answer=agent_thought.answer,  # 答案内容
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
