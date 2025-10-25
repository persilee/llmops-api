import json
from dataclasses import dataclass
from typing import Any

from injector import inject

from src.core.tools.api_tool.entities.openapi_schema import OpenAPISchema
from src.exception.exception import ValidateErrorException


@inject
@dataclass
class ApiToolService:
    """API工具服务类，用于处理OpenAPI规范相关的操作"""

    @classmethod
    def _validate_dict_format(cls, data: Any) -> None:
        """验证数据是否为字典类型

        Args:
            data: 需要验证的数据

        Raises:
            ValidateErrorException: 当数据不是字典类型时抛出

        """
        if not isinstance(data, dict):
            error_msg = "数据必须是一个字典类型"
            raise ValidateErrorException(error_msg)

    @classmethod
    def parse_openapi_schema(cls, openapi_schema_srt: str) -> OpenAPISchema:
        """解析OpenAPI规范格式的JSON字符串

        Args:
            openapi_schema_srt: OpenAPI规范的JSON字符串

        Returns:
            OpenAPISchema: 解析后的OpenAPI模式对象

        Raises:
            ValidateErrorException: 当输入不是有效的JSON格式或不是字典类型时抛出

        """
        try:
            data = json.loads(openapi_schema_srt.strip())
            cls._validate_dict_format(data)
        except json.JSONDecodeError as e:
            error_msg = "数据必须符合 openapi 规范的 json 格式"
            raise ValidateErrorException(error_msg) from e

        return OpenAPISchema(**data)
