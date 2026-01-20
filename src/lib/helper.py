import importlib
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from hashlib import sha3_256
from pathlib import Path
from typing import Any
from uuid import UUID

from flask import current_app
from langchain_core.documents import Document
from pydantic import BaseModel, HttpUrl


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


def combine_documents(documents: list[Document]) -> str:
    """将多个文档合并为一个字符串

    Args:
        documents (list[Document]): 要合并的文档列表

    Returns:
        str: 合并后的字符串，每个文档之间用两个换行符分隔

    """
    return "\n\n".join([document.page_content for document in documents])


def remove_fields(data_dict: dict, fields: list[str]) -> None:
    """从字典中移除指定的字段。

    Args:
        data_dict (dict): 要修改的字典
        fields (list[str]): 要移除的字段列表

    Returns:
        None: 直接修改原字典，无返回值

    """
    for field in fields:
        data_dict.pop(field, None)


def convert_model_to_dict(obj: Any, *args: Any, **kwargs: Any) -> dict:
    """辅助函数，将Pydantic V1版本中的UUID/Enum等数据转换成可序列化存储的数据。"""
    # 1.如果是Pydantic的BaseModel类型，递归处理其字段
    if isinstance(obj, BaseModel):
        obj_dict = obj.model_dump(*args, **kwargs)
        # 2.递归处理嵌套字段
        for key, value in obj_dict.items():
            obj_dict[key] = convert_model_to_dict(value, *args, **kwargs)
        return obj_dict

    # 3.如果是 UUID 类型，转换为字符串
    if isinstance(obj, UUID):
        return str(obj)

    # 4.如果是 Enum 类型，转换为其值
    if isinstance(obj, Enum):
        return obj.value

    # 5.如果是列表类型，递归处理列表中的每个元素
    if isinstance(obj, list):
        return [convert_model_to_dict(item, *args, **kwargs) for item in obj]

    # 6.如果是字典类型，递归处理字典中的每个字段
    if isinstance(obj, dict):
        return {
            key: convert_model_to_dict(value, *args, **kwargs)
            for key, value in obj.items()
        }

    # 7.对其他类型的字段，保持原样
    return obj


def make_serializable(obj: Any) -> Any:
    """将对象转换为可序列化的格式。

    递归处理对象，确保所有嵌套结构都可以被序列化。

    Args:
        obj (Any): 需要序列化的对象

    Returns:
        Any: 可序列化的对象

    处理规则：
        1. HttpUrl类型转换为字符串
        2. 字典类型递归处理每个键值对
        3. 列表类型递归处理每个元素
        4. 其他类型保持原样

    """
    if isinstance(obj, HttpUrl):
        return str(obj)
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_serializable(item) for item in obj]
    return obj


def get_value_type(value: Any) -> Any:
    """根据传递的值获取变量的类型，并将str和bool转换成string和boolean"""
    # 1.计算变量的类型并转换成字符串
    value_type = type(value).__name__

    # 2.判断是否为str或者是bool
    if value_type == "str":
        return "string"
    if value_type == "bool":
        return "boolean"

    return value_type
