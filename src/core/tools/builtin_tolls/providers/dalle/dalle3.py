from typing import Any

from langchain_community.tools.openai_dalle_image_generation import (
    OpenAIDALLEImageGenerationTool,
)
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from pydantic import BaseModel, Field

from src.lib.helper import add_attribute


class Dalle3ArgsSchema(BaseModel):
    query: str = Field(description="需要生成图片的描述")


@add_attribute("args_schema", Dalle3ArgsSchema)
def dalle3(**kwargs: dict[str, Any]) -> OpenAIDALLEImageGenerationTool:
    """返回DALLE3绘图工具"""
    return OpenAIDALLEImageGenerationTool(
        api_wrapper=DallEAPIWrapper(model="dall-e-3", **kwargs),
        args_schema=Dalle3ArgsSchema,
    )
