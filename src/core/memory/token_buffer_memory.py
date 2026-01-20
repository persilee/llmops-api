from dataclasses import dataclass

from langchain.messages import AIMessage, AnyMessage, HumanMessage, trim_messages
from langchain_core.messages import get_buffer_string
from sqlalchemy import desc

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.llm_model.entities.model_entity import BaseLanguageModel
from src.entity.conversation_entity import MessageStatus
from src.model.conversation import Conversation, Message


@dataclass
class TokenBufferMemory:
    db: SQLAlchemy
    conversation: Conversation
    model_instance: BaseLanguageModel

    def get_history_prompt_messages(
        self,
        max_token_limit: int = 2000,
        message_limit: int = 10,
    ) -> list[AnyMessage]:
        """获取历史对话消息并转换为提示消息格式

        Args:
            max_token_limit (int): 最大token限制，默认为2000
            message_limit (int): 消息数量限制，默认为10

        Returns:
            list[AnyMessage]: 经过token限制处理后的消息列表，包含HumanMessage和AIMessage

        """
        if self.conversation is None:
            return []

        # 从数据库查询消息，按创建时间倒序排列
        messages = (
            self.db.session.query(Message)
            .filter(
                Message.conversation_id == self.conversation.id,
                Message.answer != "",
                not Message.is_deleted,
                Message.status.in_(
                    [MessageStatus.NORMAL, MessageStatus.STOP, MessageStatus.TIMEOUT],
                ),
            )
            .order_by(desc("created_at"))
            .limit(message_limit)
            .all()
        )

        # 将消息列表反转，使其按时间正序排列
        messages = list(reversed(messages))

        # 将数据库消息转换为提示消息格式
        prompt_messages = []
        for message in messages:
            prompt_messages.extend(
                [
                    HumanMessage(content=message.query),
                    AIMessage(content=message.answer),
                ],
            )

        # 使用trim_messages对消息进行token限制处理
        return trim_messages(
            messages=prompt_messages,
            max_tokens=max_token_limit,
            token_counter=self.model_instance,
            strategy="last",
            start_on="human",
            end_on="ai",
        )

    def get_history_prompt_text(
        self,
        human_prefix: str = "Human",
        ai_prefix: str = "AI",
        max_token_limit: int = 2000,
        message_limit: int = 10,
    ) -> str:
        """获取历史对话消息并转换为文本格式

        Args:
            human_prefix (str): 人类消息前缀，默认为"Human"
            ai_prefix (str): AI消息前缀，默认为"AI"
            max_token_limit (int): 最大token限制，默认为2000
            message_limit (int): 消息数量限制，默认为10

        Returns:
            str: 格式化后的历史对话文本

        """
        # 获取经过token限制处理后的历史消息列表
        messages = self.get_history_prompt_messages(max_token_limit, message_limit)

        # 将消息列表转换为格式化的文本字符串
        return get_buffer_string(messages, human_prefix, ai_prefix)
