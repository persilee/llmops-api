from typing import Any

from pkg.swagger.swagger import model_to_swagger_schema, wtform_to_flasgger_definition

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


def form_schema(cls) -> type:
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
