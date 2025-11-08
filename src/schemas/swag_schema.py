from typing import Any

from pkg.swagger.swagger import (
    marshmallow_to_openapi_schema,
    model_to_swagger_schema,
    wtform_to_flasgger_definition,
)

# 存储生成的 Swagger 模式
swag_schemas: dict[str, dict[str, Any]] = {}


def swagger_schema(cls) -> type:
    """为 SQLAlchemy 模型生成 Swagger 模式的类装饰器

    Args:
        cls: SQLAlchemy 模型类

    Returns:
        原模型类（未修改）

    """
    # 使用模型名作为模式名
    schema_name = cls.__name__

    # 生成 Swagger 模式
    swag_schema = model_to_swagger_schema(cls)

    # 将模式添加到 schemas 字典
    swag_schemas[schema_name] = swag_schema

    return cls


def req_schema(cls) -> type:
    """装饰器：将WTForms表单类转换为Flasgger定义并注册

    Args:
        cls: WTForms表单类

    """
    schema_name = cls.__name__

    # 转换为Flasgger定义
    flasgger_definition = wtform_to_flasgger_definition(cls)

    # 将模式添加到 schemas 字典
    swag_schemas[schema_name] = flasgger_definition

    return cls


def resp_schema(schema_name=None, field_descriptions=None) -> Any:
    """装饰器：将Marshmallow Schema类转换为OpenAPI 3 Schema并注册

    Args:
        schema_name: Schema名称（可选）
        field_descriptions: 字段描述字典（可选），格式：{字段名: 描述}

    """

    def decorator(schema_class) -> Any:
        # 转换为OpenAPI Schema
        openapi_schema = marshmallow_to_openapi_schema(schema_class)

        # 添加自定义字段描述
        if field_descriptions:
            for field_name, description in field_descriptions.items():
                if field_name in openapi_schema["properties"]:
                    openapi_schema["properties"][field_name]["description"] = (
                        description
                    )

        # 使用类名作为Schema名称（如果未指定）
        if schema_name is None:
            schema_name_final = schema_class.__name__
        else:
            schema_name_final = schema_name

        # 将模式添加到 schemas 字典
        swag_schemas[schema_name_final] = openapi_schema

        # 将OpenAPI Schema附加到原始类
        schema_class.openapi_schema = openapi_schema
        schema_class.schema_name = schema_name_final

        return schema_class

    return decorator
