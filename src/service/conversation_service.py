import logging
from dataclasses import dataclass

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from pkg.sqlalchemy import SQLAlchemy
from src.entity.conversation_entity import (
    CONVERSATION_NAME_TEMPLATE,
    MAX_CONVERSATION_NAME_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_SUGGESTED_QUESTIONS,
    SUGGESTED_QUESTIONS_TEMPLATE,
    SUMMARIZER_TEMPLATE,
    TRUNCATE_PREFIX_LENGTH,
    ConversationInfo,
    SuggestedQuestions,
)
from src.service.base_service import BaseService

logger = logging.getLogger(__name__)


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
