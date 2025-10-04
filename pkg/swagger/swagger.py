import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, ColumnDefault
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


def _get_column_example(column: Column) -> str | None:
    """获取列的示例值"""
    if column.default is None:
        return None

    result = None
    try:
        if hasattr(column, "info") and "example" in column.info:
            # 使用模型中定义的示例值
            return column.info["example"]

        if isinstance(column.default, ColumnDefault):
            default_value = column.default.arg
        else:
            default_value = column.default

        if callable(default_value):
            if default_value.__name__ == "uuid4":
                result = str(uuid.uuid4())
            elif default_value.__name__ == "now":
                result = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            elif default_value.__name__ == "func":
                result = default_value()
            elif default_value == "":
                result = None
        elif default_value is not None and default_value != "":
            result = str(default_value)

    except (ValueError, TypeError):
        pass

    return result
