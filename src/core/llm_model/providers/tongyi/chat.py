from langchain_community.chat_models.tongyi import ChatTongyi

from src.core.llm_model.entities.model_entity import BaseLanguageModel


class Chat(ChatTongyi, BaseLanguageModel):
    """通义千问聊天模型"""
