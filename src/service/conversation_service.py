from dataclasses import dataclass

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from pkg.sqlalchemy import SQLAlchemy
from src.entity.conversation_entity import SUMMARIZER_TEMPLATE
from src.service.base_service import BaseService


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
