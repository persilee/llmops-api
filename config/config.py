import os
from typing import Any

from config.default_config import DEFAULT_CONFIG


def _get_env(key: str) -> Any:
    """从环境变量或默认配置中获取指定键的值。

    该函数首先尝试从环境变量中获取指定键的值，如果环境变量中不存在该键，
    则从默认配置字典 DEFAULT_CONFIG 中获取对应的值。

    Args:
        key (str): 要查找的配置键名

    Returns:
        Any: 找到的配置值，类型取决于配置值的实际类型

    Note:
        - 该函数会依次查找环境变量和默认配置
        - 如果在环境变量和默认配置中都找不到该键，将返回 None
        - 支持处理包含特殊字符的键名，包括 //t (制表符)、//r (回车符) 和 //n (换行符)

    """
    return os.getenv(key, DEFAULT_CONFIG.get(key))


def _get_bool_env(key: str) -> bool:
    """从环境变量中获取指定键的布尔值。

    该函数通过键名从环境变量中获取对应的字符串值，并将其转换为布尔值。
    当环境变量值为字符串"true"（不区分大小写）时返回True，否则返回False。
    如果环境变量不存在（值为None），则默认返回False。

    参数:
        key (str): 要获取的环境变量的键名

    返回:
        bool: 环境变量对应的布尔值，如果环境变量不存在则返回False

    示例:
        >>> # 假设环境变量 DEBUG="true"
        >>> _get_bool_env("DEBUG")
        True
        >>> # 假设环境变量 TEST_MODE="False"
        >>> _get_bool_env("TEST_MODE")
        False
        >>> # 假设环境变量 UNSET_VAR 不存在
        >>> _get_bool_env("UNSET_VAR")
        False
    """
    value: str = _get_env(key)
    return value.lower() == "true" if value is not None else False


class Config:
    def __init__(self) -> None:
        # 将CSRF（跨站请求伪造）保护设置为禁用状态
        self.WTF_CSRF_ENABLED = _get_bool_env("WTF_CSRF_ENABLED")

        # 数据库配置
        self.SQLALCHEMY_DATABASE_URI = _get_env("SQLALCHEMY_DATABASE_URI")
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": int(_get_env("SQLALCHEMY_POOL_SIZE")),
            "pool_recycle": int(_get_env("SQLALCHEMY_POOL_RECYCLE")),
        }
        self.SQLALCHEMY_ECHO = _get_bool_env("SQLALCHEMY_ECHO")

        # Redis配置
        self.REDIS_HOST = _get_env("REDIS_HOST")
        self.REDIS_PORT = int(_get_env("REDIS_PORT"))
        self.REDIS_USERNAME = _get_env("REDIS_USERNAME")
        self.REDIS_PASSWORD = _get_env("REDIS_PASSWORD")
        self.REDIS_DB = int(_get_env("REDIS_DB"))
        self.REDIS_USE_SSL = _get_bool_env("REDIS_USE_SSL")

        # Celery配置
        self.CELERY = {
            "broker_url": f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{int(_get_env('CELERY_BROKER_DB'))}",
            "result_backend": f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{int(_get_env('CELERY_RESULT_BACKEND_DB'))}",
            "task_ignore_result": _get_bool_env("CELERY_TASK_IGNORE_RESULT"),
            "result_expires": int(_get_env("CELERY_RESULT_EXPIRES")),
            "broker_connection_retry_on_startup": _get_bool_env(
                "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
            ),
        }

        # 辅助Agent应用id标识
        self.ASSISTANT_AGENT_ID = _get_env("ASSISTANT_AGENT_ID")
