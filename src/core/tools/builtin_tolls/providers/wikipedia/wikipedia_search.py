from typing import Any

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import BaseTool


def wikipedia_search(**kwargs: dict[str, Any]) -> BaseTool:
    """搜索维基百科工具"""
    return WikipediaQueryRun(
        api_wrapper=WikipediaAPIWrapper(),
    )
