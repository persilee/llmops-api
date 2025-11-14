import uuid
from datetime import UTC, datetime
from typing import Any

from marshmallow import fields
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
from wtforms import (
    BooleanField,
    DateField,
    DateTimeField,
    EmailField,
    FloatField,
    IntegerField,
    TimeField,
)
from wtforms.fields.core import UnboundField
from wtforms.validators import URL, DataRequired, Email, Length, NumberRange

from src.lib.helper import get_root_path


def get_swagger_path(relative_path: str) -> str:
    """获取 Swagger 文档的绝对路径"""
    # 获取项目根目录
    root_path = get_root_path()
    return str(root_path / "docs" / relative_path)


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

    data_warper: dict[str, Any] = {
        "type": "object",
        "required": ["data"],
        "properties": {
            "data": schema,
        },
    }

    return data_warper


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


def _process_validator(
    field_def: dict,
    validator,
    field_name: str,
    definition: dict,
) -> None:
    """处理单个验证器"""
    validator_handlers = {
        DataRequired: lambda: _handle_data_required(
            validator,
            field_name,
            definition,
            field_def,
        ),
        Length: lambda: _handle_length(validator, field_def),
        URL: lambda: _handle_url(validator, field_def),
        Email: lambda: _handle_email(validator, field_def),
        NumberRange: lambda: _handle_number_range(validator, field_def),
    }

    handler = validator_handlers.get(type(validator))
    if handler:
        handler()


def _handle_data_required(
    validator,
    field_name: str,
    definition: dict,
    field_def: dict,
) -> None:
    """处理DataRequired验证器"""
    if field_name not in definition["required"]:
        definition["required"].append(field_name)
    if hasattr(validator, "message") and validator.message:
        field_def["description"] = validator.message


def _handle_length(validator, field_def: dict) -> None:
    """处理Length验证器"""
    if validator.max:
        field_def["maxLength"] = validator.max
    if validator.min:
        field_def["minLength"] = validator.min
    if hasattr(validator, "message") and validator.message:
        field_def["description"] = validator.message


def _handle_url(validator, field_def: dict) -> None:
    """处理URL验证器"""
    field_def["format"] = "uri"
    if hasattr(validator, "message") and validator.message:
        field_def["description"] = validator.message


def _handle_email(validator, field_def: dict) -> None:
    """处理Email验证器"""
    field_def["format"] = "email"
    if hasattr(validator, "message") and validator.message:
        field_def["description"] = validator.message


def _handle_number_range(validator, field_def: dict) -> None:
    """处理NumberRange验证器"""
    if validator.max:
        field_def["maximum"] = validator.max
    if validator.min:
        field_def["minimum"] = validator.min
    if hasattr(validator, "message") and validator.message:
        field_def["description"] = validator.message


def wtform_to_flasgger_definition(form_class) -> dict[str, Any]:
    """将WTForms表单类转换为Flasgger定义（支持WTForms 3.2.1版本）

    Args:
        form_class: WTForms表单类

    Returns:
        dict: Flasgger定义

    """
    definition = {"type": "object", "properties": {}, "required": []}

    # 遍历表单类的所有属性
    for name in dir(form_class):
        if not name.startswith("_"):
            attr = getattr(form_class, name)

            # 检查是否是UnboundField
            if isinstance(attr, UnboundField):
                field_name = name
                field_type = attr.field_class
                field_args = attr.kwargs

                # 创建字段定义
                field_def = {
                    "type": "string",
                    "description": field_args.get("description", field_name),
                }

                field_def = _process_field_type(field_def, field_type)

                # 处理验证器
                validators = field_args.get("validators", [])
                for validator in validators:
                    _process_validator(field_def, validator, field_name, definition)

                # 添加默认值
                if "default" in field_args:
                    field_def["default"] = field_args["default"]

                definition["properties"][field_name] = field_def

    return definition


def _process_field_type(field_def: dict, field_type: Any) -> dict:
    from src.schemas.schema import DictField, ListField

    # 根据字段类型设置格式
    if field_type == EmailField:
        field_def["format"] = "email"
    elif field_type == IntegerField:
        field_def["type"] = "integer"
    elif field_type == FloatField:
        field_def["type"] = "number"
    elif field_type == BooleanField:
        field_def["type"] = "boolean"
    elif field_type == ListField:
        field_def["type"] = "array"
    elif field_type == DictField:
        field_def["type"] = "object"
    elif field_type == DateTimeField:
        field_def["format"] = "date-time"
    elif field_type == DateField:
        field_def["format"] = "date"
    elif field_type == TimeField:
        field_def["format"] = "time"

    return field_def


def clean_schema_for_json(schema_dict) -> dict | list | str | int | float | bool | None:
    """清理Schema字典中的不可JSON序列化的值"""
    if isinstance(schema_dict, dict):
        cleaned = {}
        for k, v in schema_dict.items():
            if v is not None:
                cleaned_v = clean_schema_for_json(v)
                if cleaned_v is not None:
                    cleaned[k] = cleaned_v
        return cleaned
    if isinstance(schema_dict, list):
        cleaned = []
        for item in schema_dict:
            cleaned_item = clean_schema_for_json(item)
            if cleaned_item is not None:
                cleaned.append(cleaned_item)
        return cleaned
    # 检查是否是可JSON序列化的基本类型
    if isinstance(schema_dict, (str, int, float, bool)):
        return schema_dict
    # 对于不可序列化的类型，返回None或转换为字符串
    try:
        return str(schema_dict)
    except (ValueError, TypeError):
        return None


def get_field_schema(field_obj, field_name=None) -> dict:  # noqa: PLR0912, PLR0915
    """递归获取字段的OpenAPI Schema定义

    Args:
        field_obj: Marshmallow字段对象
        field_name: 字段名称（用于生成示例）

    Returns:
        dict: 字段的OpenAPI Schema定义

    """
    field_schema = {}

    # 处理List类型
    if isinstance(field_obj, fields.List):
        field_schema["type"] = "array"
        # 获取列表项的Schema
        if hasattr(field_obj, "_inner") and field_obj._inner:  # noqa: SLF001
            inner_schema = get_field_schema(
                field_obj._inner,  # noqa: SLF001
                f"{field_name}_item" if field_name else "item",
            )
            field_schema["items"] = inner_schema
        else:
            # 默认数组项为object类型
            field_schema["items"] = {"type": "object"}

        # 添加示例值
        field_schema["example"] = []
        if field_name == "headers":
            field_schema["example"] = [
                {"Authorization": "Bearer token", "Content-Type": "application/json"},
            ]
        elif field_name == "tools":
            field_schema["example"] = [
                {"id": "tool1", "name": "示例工具", "description": "这是一个示例工具"},
            ]

        return field_schema

    # 处理Dict类型
    if isinstance(field_obj, fields.Dict):
        field_schema["type"] = "object"
        field_schema["additionalProperties"] = True

        # 添加示例值
        if field_name and "header" in field_name.lower():
            field_schema["example"] = {"Authorization": "Bearer token"}
        else:
            field_schema["example"] = {"key": "value"}

        return field_schema

    # 处理UUID类型
    if isinstance(field_obj, fields.UUID):
        field_schema["type"] = "string"
        field_schema["format"] = "uuid"
        field_schema["example"] = "123e4567-e89b-12d3-a456-426614174000"

    # 处理String类型
    elif isinstance(field_obj, fields.String):
        field_schema["type"] = "string"
        if field_name and "url" in field_name.lower():
            field_schema["format"] = "uri"
            field_schema["example"] = "https://example.com/icon.png"
        else:
            field_schema["example"] = (
                f"example_{field_name}" if field_name else "example_value"
            )

    # 处理Integer类型
    elif isinstance(field_obj, fields.Integer):
        field_schema["type"] = "integer"
        if field_name and "timestamp" in field_name.lower():
            field_schema["description"] = "时间戳（秒）"
            field_schema["example"] = 1620000000
        else:
            field_schema["example"] = 0

    # 处理Boolean类型
    elif isinstance(field_obj, fields.Boolean):
        field_schema["type"] = "boolean"
        field_schema["example"] = False

    # 处理Float类型
    elif isinstance(field_obj, fields.Float):
        field_schema["type"] = "number"
        field_schema["format"] = "float"
        field_schema["example"] = 0.0

    # 处理DateTime类型
    elif isinstance(field_obj, fields.DateTime):
        field_schema["type"] = "string"
        field_schema["format"] = "date-time"
        field_schema["example"] = "2024-01-01T00:00:00Z"

    # 处理Date类型
    elif isinstance(field_obj, fields.Date):
        field_schema["type"] = "string"
        field_schema["format"] = "date"
        field_schema["example"] = "2024-01-01"

    # 处理Time类型
    elif isinstance(field_obj, fields.Time):
        field_schema["type"] = "string"
        field_schema["format"] = "time"
        field_schema["example"] = "00:00:00"

    # 处理Email类型
    elif isinstance(field_obj, fields.Email):
        field_schema["type"] = "string"
        field_schema["format"] = "email"
        field_schema["example"] = "user@example.com"

    # 处理URL类型
    elif isinstance(field_obj, fields.URL):
        field_schema["type"] = "string"
        field_schema["format"] = "uri"
        field_schema["example"] = "https://example.com"

    # 默认类型处理
    else:
        field_schema["type"] = "string"
        field_schema["example"] = (
            f"example_{field_name}" if field_name else "example_value"
        )

    return field_schema


def marshmallow_to_openapi_schema(schema_class) -> dict[str, Any]:
    """将Marshmallow Schema类转换为OpenAPI 3 Schema

    Args:
        schema_class: Marshmallow Schema类

    Returns:
        dict: OpenAPI 3 Schema

    """
    openapi_schema = {"type": "object", "properties": {}, "required": []}

    # 获取Schema类的所有字段
    schema_instance = schema_class()
    fields_dict = schema_instance.fields

    for field_name, field_obj in fields_dict.items():
        # 获取字段的详细Schema
        field_schema = get_field_schema(field_obj, field_name)

        # 添加描述 - 使用字段名的友好版本作为默认描述
        field_schema["description"] = field_name.replace("_", " ")

        # 添加默认值（处理特殊情况）
        if hasattr(field_obj, "dump_default") and field_obj.dump_default is not None:
            # 处理dump_default是函数的情况
            if callable(field_obj.dump_default):
                try:
                    default_value = field_obj.dump_default()
                    # 清理默认值，确保可JSON序列化
                    cleaned_default = clean_schema_for_json(default_value)
                    if cleaned_default is not None:
                        field_schema["default"] = cleaned_default
                except (ValueError, TypeError):
                    # 如果函数调用失败，不设置默认值
                    pass
            else:
                # 清理默认值，确保可JSON序列化
                cleaned_default = clean_schema_for_json(field_obj.dump_default)
                if cleaned_default is not None:
                    field_schema["default"] = cleaned_default

        # 检查是否为必填字段
        if hasattr(field_obj, "required") and field_obj.required:
            openapi_schema["required"].append(field_name)

        openapi_schema["properties"][field_name] = field_schema

    return openapi_schema
