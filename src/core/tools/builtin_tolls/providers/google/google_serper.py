from typing import Any

from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class GoogleSerperArgsSchema(BaseModel):
    """谷歌serper搜索参数"""

    query: str = Field(description="搜索关键词")


def google_serper(**kwargs: dict[str, Any]) -> BaseTool:
    """谷歌 serper 搜索"""
    return GoogleSerperRun(
        name="google_serper",
        description="这是一个谷歌搜索工具，可以搜索互联网上的信息",
        args_schema=GoogleSerperArgsSchema,
        api_wrapper=GoogleSerperAPIWrapper(),
    )
