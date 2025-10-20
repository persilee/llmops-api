from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import BaseTool


class CurrentTimeTool(BaseTool):
    """获取当前时间的工具类。

    继承自BaseTool，提供获取当前时间的功能。
    返回的时间格式为：YYYY-MM-DD HH:MM:SS 时区
    """

    name: str = "current_time"  # 工具名称
    description: str = "获取当前时间的工具"

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """执行获取当前时间的操作。

        Args:
            *args: 可变位置参数（未使用）
            **kwargs: 可变关键字参数（未使用）

        Returns:
            str: 格式化后的当前时间字符串，包含时区信息

        """
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S %Z")


def current_time() -> BaseTool:
    """创建一个获取当前时间的工具实例。

    Returns:
        CurrentTimeTool: 获取当前时间的工具实例

    """
    return CurrentTimeTool()
