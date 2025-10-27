from enum import Enum

from pydantic import BaseModel, Field, field_validator

from src.exception.exception import ValidateErrorException


class ParameterType(str, Enum):
    """API参数类型枚举类"""

    STR: str = "str"  # 字符串类型
    INT: str = "int"  # 整数类型
    FLOAT: str = "float"  # 浮点数类型
    BOOL: str = "bool"  # 布尔类型


# 参数类型映射字典：将OpenAPI参数类型枚举映射到对应的Python类型
ParameterTypeMap = {
    ParameterType.STR: str,  # 字符串类型映射
    ParameterType.INT: int,  # 整数类型映射
    ParameterType.FLOAT: float,  # 浮点数类型映射
    ParameterType.BOOL: bool,  # 布尔类型映射
}


class ParameterIn(str, Enum):
    """API参数位置枚举类"""

    PATH: str = "path"  # 路径参数
    QUERY: str = "query"  # 查询参数
    HEADER: str = "header"  # 请求头参数
    COOKIE: str = "cookie"  # Cookie参数
    REQUEST_BODY: str = "requestBody"  # 请求体参数


class OpenAPISchema(BaseModel):
    """OpenAPI Schema的基础模型类，用于验证和规范化API接口定义

    Attributes:
        server (str): 工具提供者的服务地址
        description (str): 工具的描述信息
        paths (dict): 工具的接口路径参数描述

    """

    server: str = Field(
        default="",
        validate_default=True,
        description="工具提供者的服务地址",
    )
    description: str = Field(
        default="",
        validate_default=True,
        description="工具的描述信息",
    )
    paths: dict[str, dict] = Field(
        default_factory=dict,
        validate_default=True,
        description="工具的接口路径参数描述",
    )

    @field_validator("server", mode="before")
    @classmethod
    def validate_server(cls, server: str) -> str:
        """验证server字段的有效性

        Args:
            server (str): 待验证的服务地址字符串

        Returns:
            str: 验证通过的服务地址

        Raises:
            ValidateErrorException: 当server为空或None时抛出

        """
        if server is None or server == "":
            error_msg = "server字符串不能为空"
            raise ValidateErrorException(error_msg)
        return server

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, description: str) -> str:
        """验证description字段的有效性

        Args:
            description (str): 待验证的描述信息字符串

        Returns:
            str: 验证通过的描述信息

        Raises:
            ValidateErrorException: 当description为空或None时抛出

        """
        if description is None or description == "":
            error_msg = "description字符串不能为空"
            raise ValidateErrorException(error_msg)
        return description

    @classmethod
    def _validate_interface_operation(
        cls,
        path: str,
        method: str,
        operation: dict,
    ) -> None:
        """验证接口操作的基本字段"""
        if not isinstance(operation.get("description"), str):
            error_msg = f"接口{path}的{method}方法description字段不能为空且为字符串"
            raise ValidateErrorException(error_msg)
        if not isinstance(operation.get("operationId"), str):
            error_msg = f"接口{path}的{method}方法operationId字段不能为空且为字符串"
            raise ValidateErrorException(error_msg)
        if not isinstance(operation.get("parameters", []), list):
            error_msg = f"接口{path}的{method}方法parameters字段不能为空且为列表"
            raise ValidateErrorException(error_msg)

    @classmethod
    def _validate_parameter(cls, path: str, method: str, parameter: dict) -> None:
        """验证单个参数的字段"""
        if not isinstance(parameter.get("name"), str):
            error_msg = (
                f"接口{path}的{method}方法parameters字段中的name字段不能为空且为字符串"
            )
            raise ValidateErrorException(error_msg)
        if not isinstance(parameter.get("description"), str):
            error_msg = (
                f"接口{path}的{method}方法"
                "parameters字段中的description字段不能为空且为字符串"
            )
            raise ValidateErrorException(error_msg)
        if not isinstance(parameter.get("required"), bool):
            error_msg = (
                f"接口{path}的{method}方法"
                "parameters字段中的required字段不能为空且为布尔值"
            )
            raise ValidateErrorException(error_msg)
        if (
            not isinstance(parameter.get("in"), str)
            or parameter.get("in") not in ParameterIn.__members__.values()
        ):
            error_msg = (
                f"接口{path}的{method}方法parameters.in"
                f"参数必须为{'/'.join([item.value for item in ParameterIn])}"
            )
            raise ValidateErrorException(error_msg)
        if (
            not isinstance(parameter.get("type"), str)
            or parameter.get("type") not in ParameterType.__members__.values()
        ):
            error_msg = (
                f"接口{path}的{method}方法parameters.type"
                f"参数必须为{'/'.join([item.value for item in ParameterType])}"
            )
            raise ValidateErrorException(error_msg)

    @classmethod
    def _build_normalized_paths(cls, interfaces: list) -> dict:
        """构建规范化后的paths字典"""
        normalized_paths = {}
        for interface in interfaces:
            normalized_paths[interface["path"]] = {
                interface["method"]: {
                    "description": interface["operation"]["description"],
                    "operationId": interface["operation"]["operationId"],
                    "parameters": [
                        {
                            "name": parameter.get("name"),
                            "in": parameter.get("in"),
                            "description": parameter.get("description"),
                            "required": parameter.get("required"),
                            "type": parameter.get("type"),
                        }
                        for parameter in interface["operation"].get("parameters", [])
                    ],
                },
            }
        return normalized_paths

    @field_validator("paths", mode="before")
    @classmethod
    def validate_paths(cls, paths: dict[str, dict]) -> dict[str, dict]:
        """验证paths字段的有效性，包括接口路径、方法、参数等"""
        if paths is None or paths == {}:
            error_msg = "paths字典不能为空"
            raise ValidateErrorException(error_msg)

        # 支持的HTTP方法
        methods = ["get", "post"]
        interfaces = []
        # 遍历所有路径，提取接口信息
        for path, path_item in paths.items():
            new_interfaces = [
                {
                    "path": path,
                    "method": method,
                    "operation": path_item[method],
                }
                for method in methods
                if method in path_item
            ]
            interfaces.extend(new_interfaces)

        operation_ids = []
        # 验证每个接口的必要字段
        for interface in interfaces:
            cls._validate_interface_operation(
                interface["path"],
                interface["method"],
                interface["operation"],
            )

            operation_id = interface["operation"]["operationId"]
            if operation_id in operation_ids:
                error_msg = (
                    f"接口{interface['path']}的{interface['method']}方法"
                    "operationId字段不能重复"
                )
                raise ValidateErrorException(error_msg)
            operation_ids.append(operation_id)

            # 验证每个参数的必要字段
            for parameter in interface["operation"].get("parameters", []):
                cls._validate_parameter(
                    interface["path"],
                    interface["method"],
                    parameter,
                )

        return cls._build_normalized_paths(interfaces)
