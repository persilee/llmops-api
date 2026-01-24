import json
from collections.abc import Generator
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from src.exception.exception import ForbiddenException
from src.model.account import Account
from src.model.conversation import Message
from src.service.base_service import BaseService
from src.service.conversation_service import ConversationService


@inject
@dataclass
class AIService(BaseService):
    db: SQLAlchemy
    conversation_service: ConversationService

    def generate_conversation_name(self, query: str) -> str:
        """根据查询生成对话名称。

        Args:
            query (str): 查询字符串

        Returns:
            str: 对话名称

        """
        return self.conversation_service.generate_conversation(query)

    def generate_suggested_questions_from_message_id(
        self,
        message_id: UUID,
        account: Account,
    ) -> list[str]:
        """根据消息ID生成相关的建议问题列表。

        Args:
            message_id (UUID): 消息的唯一标识符，用于获取特定的消息记录
            account (Account): 当前用户账户对象，用于验证权限

        Returns:
            list[str]: 建议问题列表，包含基于当前消息生成的相关问题

        Raises:
            ForbiddenException: 当消息不存在或不属于当前用户时抛出

        Note:
            该方法会首先验证消息的归属权，然后基于消息的问答内容生成建议问题。

        """
        # 根据消息ID获取消息对象
        message = self.get(Message, message_id)
        # 验证消息是否存在以及是否属于当前用户
        if not message or message.created_by != account.id:
            error_msg = "消息不存在或不是当前用户的"
            raise ForbiddenException(error_msg)

        # 构建对话历史记录，包含用户的问题和AI的回答
        histories = f"Human: {message.query}\nAI: {message.answer}"

        # 调用conversation_service生成建议问题
        return self.conversation_service.generate_suggested_questions(histories)

    @classmethod
    def optimize_prompt(cls, prompt: str) -> Generator[str, None, None]:
        r"""优化用户输入的提示词，使用流式输出返回优化结果。

        该方法使用 GPT-4o-mini 模型对输入的提示词进行优化，通过 Server-Sent Events (SSE)
        格式实时返回优化后的内容。

        Args:
            prompt (str): 需要优化的原始提示词文本

        Yields:
            str: SSE 格式的字符串，包含优化后的提示词片段。
                格式为 "event: optimize_prompt\ndata: {json_data}\n\n"
                其中 json_data 包含 optimize_prompt 字段

        Note:
            - 使用 gpt-4o-mini 模型，温度参数设置为 0.5
            - 采用流式输出，可以实时获取优化结果
            - 输出格式遵循 SSE 规范，便于前端处理

        """
        # 创建聊天提示模板，包含系统提示和用户输入
        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", OPTIMIZE_PROMPT_TEMPLATE),  # 系统角色提示词模板
                ("human", "{prompt}"),  # 用户输入的提示词占位符
            ],
        )

        # 初始化 GPT-4o-mini 模型，设置温度参数为 0.5
        # 温度参数控制输出的随机性，0.5 表示在保持创造性的同时确保输出相对稳定
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

        # 构建优化处理链：提示模板 -> 语言模型 -> 字符串输出解析器
        # 使用管道操作符 | 连接各个组件，形成完整的处理流程
        optimize_chain = prompt_template | llm | StrOutputParser()

        # 使用流式处理方式逐块生成优化后的提示词
        # stream 方法允许实时获取生成的内容，提高用户体验
        for optimize_prompt in optimize_chain.stream({"prompt": prompt}):
            # 构造 SSE (Server-Sent Events) 格式的数据
            data = {
                "optimize_prompt": optimize_prompt,  # 包含优化后的提示词片段
            }

            # 按照 SSE 格式生成响应字符串
            # event: 事件类型
            # data: JSON 格式的数据
            # \n\n: 表示消息结束
            yield f"event: optimize_prompt\ndata: {json.dumps(data)}\n\n"
