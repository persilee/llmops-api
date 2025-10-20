from typing import Any

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class DDGInput(BaseModel):
    query: str = Field(description="搜索查询字符串")


def duckduckgo_search(**kwargs: dict[str, Any]) -> BaseTool:
    """创建 DuckDuckGo 搜索工具实例。

    Args:
        **kwargs: 可选的关键字参数，包括：
            query (str): 搜索查询字符串
            region (str): 搜索地区
            lang (str): 搜索语言
            time (str): 时间范围
            max_results (int): 最大结果数

    Returns:
        BaseTool: 配置好的 DuckDuckGo 搜索工具实例

    Note:
        返回的工具实例可以用于执行 DuckDuckGo 搜索，
        支持多语言和地区定制化搜索。

    """
    return DuckDuckGoSearchRun(
        description="一个使用DuckDuckGo搜索的函数。参数包括：query（搜索查询），region（地区），lang（语言），time（时间），max_results（最大结果数）。",
        args_schema=DDGInput,
    )
