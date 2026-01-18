from langchain_openai import OpenAI

from src.core.llm_model.entities.model_entity import BaseLanguageModel


class Completion(OpenAI, BaseLanguageModel):
    """OpenAI聊天模型基类"""
