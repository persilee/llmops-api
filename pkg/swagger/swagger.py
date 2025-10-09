import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DefaultClause
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.inspection import inspect
from sqlalchemy.sql.sqltypes import (
    UUID,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql.type_api import TypeEngine


def get_swagger_path(relative_path: str) -> str:
    """获取 Swagger 文档的绝对路径"""
    # 获取项目根目录（假设 utils 目录在项目根目录下）
    project_root = Path(__file__).resolve().parent.parent.parent
    return str(project_root / "docs" / relative_path)


def model_to_swagger_schema(model: type[DeclarativeMeta]) -> dict[str, Any]:
    """从SQLAlchemy模型直接生成Swagger Schema"""
    schema = {"type": "object", "properties": {}, "required": []}

    mapper = inspect(model)

    for column in mapper.columns:
        # 将SQLAlchemy类型映射为Swagger属性
        prop = _map_column_type(column.type)

        # 添加字段描述（从模型的description或注释中获取）
        description = _get_column_description(column)
        if description:
            prop["description"] = description

        # 添加字段示例（从模型的default或注释中获取）
        example = _get_column_example(column)
        if example:
            prop["example"] = example

        # 添加字段到Swagger Schema
        schema["properties"][column.name] = prop

        # 检查是否为必填字段
        if not column.nullable:
            schema["required"].append(column.name)

    return schema


def _map_column_type(column_type: TypeEngine) -> dict[str, Any]:
    """将SQLAlchemy类型映射为Swagger属性"""
    type_mapping = {
        UUID: lambda: {"type": "string", "format": "uuid"},
        String: lambda: {"type": "string", "maxLength": column_type.length}
        if column_type.length
        else {"type": "string"},
        Text: lambda: {"type": "string"},
        DateTime: lambda: {"type": "string", "format": "date-time"},
        Integer: lambda: {"type": "integer"},
        Boolean: lambda: {"type": "boolean"},
        Float: lambda: {"type": "number", "format": "float"},
    }

    for type_class, mapper in type_mapping.items():
        if isinstance(column_type, type_class):
            return mapper()
    return {"type": "string"}


def _get_column_description(column: Column) -> str:
    """获取列的描述信息"""
    if hasattr(column, "info") and "description" in column.info:
        return column.info["description"]
    return column.doc or ""


def _get_column_example(column: Column) -> Any:
    """获取列的示例值"""
    # 1. 优先使用模型中明确指定的 example
    if hasattr(column, "info") and "example" in column.info:
        return column.info["example"]

    if hasattr(column, "server_default"):
        try:
            default_value = _extract_default_value(column.server_default)
            return _process_default_value(default_value, column.type)
        except (ValueError, TypeError, AttributeError):
            return _generate_fallback_example(column.type)
    else:
        return None


def _extract_default_value(default) -> Any:
    """提取默认值"""
    if isinstance(default, DefaultClause):
        return default.arg.text
    return default


def _process_default_value(default_value, column_type) -> Any:
    """处理默认值"""
    if isinstance(default_value, str) and default_value.startswith(
        ("CURRENT_TIMESTAMP", "uuid_generate_v4", "''::"),
    ):
        return _handle_text_clause(default_value)

    if callable(default_value):
        return _handle_callable(default_value)

    if default_value is not None:
        return _handle_direct_value(default_value, column_type)

    return None


def _handle_text_clause(text_value: str) -> Any:
    """处理文本条款"""
    if text_value.startswith("CURRENT_TIMESTAMP"):
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    if text_value.startswith("uuid_generate_v4"):
        return str(uuid.uuid4())
    if text_value.startswith("''::"):
        return ""
    if text_value.isdigit():
        return int(text_value)
    if text_value.replace(".", "", 1).isdigit():
        return float(text_value)
    return text_value.strip("'\"").split("::")[0]


def _handle_callable(default_value) -> Any:
    """处理可调用对象"""
    if default_value.__name__ in ("uuid4", "now"):
        return (
            str(uuid.uuid4())
            if default_value.__name__ == "uuid4"
            else datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        )

    if (
        hasattr(default_value, "__module__")
        and default_value.__module__ == "sqlalchemy.sql.functions"
    ):
        return (
            str(uuid.uuid4())
            if default_value.name == "uuid_generate_v4"
            else datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        )

    return None


def _handle_direct_value(default_value, column_type) -> Any:
    """处理直接的默认值"""
    type_handlers = {
        UUID: lambda: str(uuid.uuid4()),
        DateTime: lambda: datetime.now(UTC).isoformat(),
        (String, Text): lambda: "示例文本"
        if default_value == ""
        else str(default_value),
        Integer: lambda: int(default_value) if default_value != "" else 0,
        Float: lambda: float(default_value) if default_value != "" else 0.0,
        Boolean: lambda: bool(default_value),
    }

    for type_class, handler in type_handlers.items():
        if isinstance(column_type, type_class):
            return handler()
    return str(default_value)


def _generate_fallback_example(column_type) -> Any:
    """生成后备示例值"""
    type_examples = {
        UUID: lambda: str(uuid.uuid4()),
        DateTime: lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        String: lambda: f"示例{column_type.name}",
        Integer: lambda: 1,
        Float: lambda: 1.0,
        Boolean: lambda: True,
    }

    for type_class, example in type_examples.items():
        if isinstance(column_type, type_class):
            return example()
    return None
