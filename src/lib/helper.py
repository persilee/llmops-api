import importlib
from collections.abc import Callable
from datetime import datetime
from hashlib import sha3_256
from pathlib import Path
from typing import Any

from flask import current_app


def dynamic_import(module_name: str, class_name: str) -> Any:
    """动态导入模块和类

    Args:
        module_name (str): 模块名称
        class_name (str): 类名称

    Returns:
        class: 导入的类

    """
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def add_attribute(attr_name: str, attr_value: Any) -> Callable:
    """创建一个装饰器，用于给函数添加属性

    Args:
        attr_name (str): 要添加的属性名称
        attr_value (Any): 要添加的属性值

    Returns:
        Callable: 装饰器函数

    """

    def decorator(func: Callable) -> Callable:
        """装饰器函数，将属性添加到被装饰的函数上

        Args:
            func (Callable): 被装饰的函数

        Returns:
            Callable: 装饰后的函数

        """
        setattr(func, attr_name, attr_value)
        return func

    return decorator


def get_root_path() -> str:
    """获取根路径

    Returns:
        str: 根路径

    """
    try:
        return Path(current_app.root_path).parent.parent
    except RuntimeError:
        return Path(__file__).parent.parent.parent


def generate_text_hash(text: str) -> str:
    """生成文本的哈希值

    Args:
        text (str): 要生成哈希值的文本

    Returns:
        str: 生成的哈希值

    """
    text = str(text) + "None"
    return sha3_256(text.encode()).hexdigest()


def datetime_to_timestamp(dt: datetime) -> int:
    """将datetime对象转换为时间戳

    Args:
        dt (datetime): datetime对象

    Returns:
        int: 时间戳

    """
    if dt is None:
        return 0

    return int(dt.timestamp())
