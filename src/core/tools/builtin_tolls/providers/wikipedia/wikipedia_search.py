from typing import Any

from langchain_community.tools.wikipedia.tool import (
    WikipediaQueryInput,
    WikipediaQueryRun,
)
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import BaseTool

from src.lib.helper import add_attribute


@add_attribute("args_schema", WikipediaQueryInput)
def wikipedia_search(**kwargs: dict[str, Any]) -> BaseTool:
    """搜索维基百科工具"""
    return WikipediaQueryRun(
        api_wrapper=WikipediaAPIWrapper(),
    )
