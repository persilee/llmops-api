import mimetypes
from dataclasses import dataclass
from typing import Any

from injector import inject
from pydantic import BaseModel

from src.core.tools.builtin_tools.categories import BuiltinCategoryManager
from src.core.tools.builtin_tools.providers import BuiltinProviderManager
from src.exception.exception import NotFoundException
from src.lib.helper import get_root_path


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
    builtin_category_manager: BuiltinCategoryManager

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

    def get_provider_icon(self, provider_name: str) -> tuple[bytes, str]:
        """获取指定提供商的图标文件内容和MIME类型

        Args:
            provider_name (str): 提供商名称

        Returns:
            tuple[bytes, str]: 返回一个元组，包含图标文件的字节数据和对应的MIME类型

        Raises:
            NotFoundException: 当提供商不存在或图标文件不存在时抛出

        """
        # 获取指定的提供商实例
        provider = self.builtin_provider_manager.get_provider(provider_name)
        # 检查提供商是否存在
        if not provider:
            error_message = f"提供商{provider_name}不存在"
            # 如果提供商不存在，抛出 NotFoundException 异常
            raise NotFoundException(error_message)

        # 获取项目根路径
        root_path = get_root_path()
        # 构建提供商目录的完整路径
        provider_path = (
            root_path
            / "src"
            / "core"
            / "tools"
            / "builtin_tools"
            / "providers"
            / provider_name
        )
        # 构建图标文件的完整路径
        icon_path = provider_path / "_asset" / provider.provider_entity.icon
        # 检查图标文件是否存在
        if not icon_path.exists():
            error_message = f"提供商{provider_name}图标不存在"
            # 如果图标文件不存在，抛出 NotFoundException 异常
            raise NotFoundException(error_message)

        # 根据文件扩展名猜测 MIME 类型
        mimetype, _ = mimetypes.guess_type(icon_path)
        # 如果无法猜测类型，使用默认的二进制流类型
        mimetype = mimetype or "application/octet-stream"

        # 以二进制模式打开图标文件
        with icon_path.open("rb") as f:
            # 读取文件内容并返回文件字节数据和对应的 MIME 类型
            return f.read(), mimetype

    def get_categories(self) -> list[str, Any]:
        """获取所有内置工具的分类信息

        Returns:
            list[dict]: 返回分类信息列表，每个分类包含以下字段：
                - name: 分类名称
                - category: 分类类别
                - icon: 分类图标

        """
        # 从分类管理器获取完整的分类映射
        category_map = self.builtin_category_manager.get_category_map()

        # 将分类映射转换为字典列表格式
        return [
            {
                # 提取分类实体的名称
                "name": category["entity"].name,
                # 提取分类实体的类别
                "category": category["entity"].category,
                # 提取分类的图标信息
                "icon": category["icon"],
            }
            # 遍历所有分类值
            for category in category_map.values()
        ]
