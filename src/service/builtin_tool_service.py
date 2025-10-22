from dataclasses import dataclass
from typing import Any

from injector import inject
from pydantic import BaseModel

from src.core.tools.builtin_tolls.providers import BuiltinProviderManager
from src.exception.exception import NotFoundException


@inject
@dataclass
class BuiltinToolService:
    """内置工具服务类

    该类负责管理和提供内置工具的相关服务，包括：
    - 获取所有内置工具的列表信息
    - 构建工具提供者的详细信息
    - 构建具体工具的详细信息
    - 构建工具的输入参数信息
    - 获取特定提供商的特定工具信息

    Attributes:
        builtin_provider_manager: 内置工具提供者管理器实例，用于管理所有内置工具提供者

    """

    builtin_provider_manager: BuiltinProviderManager

    def get_builtin_tools(self) -> list[dict[str, Any]]:
        """获取所有内置工具的列表

        Returns:
            List[Dict[str, Any]]: 包含所有内置工具信息的列表，每个工具提供者包含以下
            字段：
                - name: 提供者名称
                - description: 提供者描述
                - tools: 工具列表，每个工具包含：
                    - name: 工具名称
                    - description: 工具描述
                    - inputs: 输入参数列表，每个参数包含：
                        - name: 参数名
                        - description: 参数描述
                        - required: 是否必填
                        - type: 参数类型

        """
        providers = self.builtin_provider_manager.get_providers()
        return [self._build_provider_info(provider) for provider in providers]

    def _build_provider_info(self, provider) -> dict[str, Any]:
        """构建提供者信息

        Args:
            provider: 工具提供者实例

        Returns:
            Dict[str, Any]: 包含提供者信息和其工具列表的字典

        """
        provider_entity = provider.provider_entity

        return {
            **provider_entity.model_dump(exclude=["icon"]),
            "tools": [
                self._build_tool_info(provider, tool_entity)
                for tool_entity in provider.get_tool_entities()
            ],
        }

    def _build_tool_info(self, provider, tool_entity) -> dict[str, Any]:
        """构建工具信息

        Args:
            provider: 工具提供者实例
            tool_entity: 工具实体

        Returns:
            Dict[str, Any]: 包含工具信息和其参数列表的字典

        """
        return {
            **tool_entity.model_dump(),
            "inputs": self._build_tool_inputs(provider, tool_entity.name),
        }

    def _build_tool_inputs(self, provider, tool_name: str) -> list[dict[str, Any]]:
        """构建工具输入参数信息

        Args:
            provider: 工具提供者实例
            tool_name: 工具名称

        Returns:
            List[Dict[str, Any]]: 工具输入参数列表

        """
        tool = provider.get_tool(tool_name)
        if not (
            hasattr(tool, "args_schema") and issubclass(tool.args_schema, BaseModel)
        ):
            return []

        return [
            {
                "name": field_name,
                "description": model_field.description or "",
                "required": model_field.is_required(),
                "type": model_field.annotation.__name__,
            }
            for field_name, model_field in tool.args_schema.model_fields.items()
        ]

    def get_builtin_tool(self, provider_name: str, tool_name: str) -> dict:
        """获取指定提供商的特定工具信息

        Args:
            provider_name: 提供商名称
            tool_name: 工具名称

        Returns:
            dict: 包含工具信息的字典，结构如下：
                - provider: 提供商信息（不包含icon字段）
                - 工具实体信息
                - inputs: 工具输入参数列表

        Raises:
            NotFoundException: 当提供商或工具不存在时抛出

        """
        # 获取指定的提供商
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is None:
            error_message = f"提供商{provider_name}不存在"
            raise NotFoundException(error_message)

        # 获取指定的工具实体
        tool_entity = provider.get_tool_entity(tool_name)
        if tool_entity is None:
            error_message = f"提供商{provider_name}下工具{tool_name}不存在"
            raise NotFoundException(error_message)

        # 获取提供商实体信息
        provider_entity = provider.provider_entity

        # 构建并返回完整的工具信息
        return {
            "provider": {**provider_entity.model_dump(exclude=["icon", "created_at"])},
            **tool_entity.model_dump(),
            "created_at": provider_entity.created_at,
            "inputs": self._build_tool_inputs(provider, tool_name),
        }
