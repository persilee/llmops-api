from asyncio.log import logger
from pathlib import Path
from typing import Any, ClassVar

import yaml
from injector import inject, singleton

from src.core.tools.builtin_tolls.entities import ProviderEntity
from src.core.tools.builtin_tolls.entities.provider_entity import Provider


@inject
@singleton
class ProviderFactory:
    """服务提供者工厂"""

    provider_map: ClassVar[dict[str, Provider]] = {}

    def __init__(self) -> None:
        self._get_provider_tool_map()

    def get_provider(self, provider_name: str) -> Provider:
        """获取服务提供者实例"""
        return self.provider_map.get(provider_name)

    def get_providers(self) -> list[Provider]:
        """获取所有服务提供者实例"""
        return list(self.provider_map.values())

    def get_provider_entity(self) -> list[ProviderEntity]:
        """获取所有服务提供者实体"""
        return [provider.provider_entity for provider in self.provider_map.values()]

    def get_tool(self, provider_name: str, tool_name: str) -> Any:
        """获取工具函数"""
        provider = self.get_provider(provider_name)
        return provider.get_tool(tool_name) if provider else None

    def _get_provider_tool_map(self) -> None:
        """获取服务提供者工具映射"""
        if self.provider_map:
            return

        try:
            # 获取当前文件所在目录的绝对路径
            current_path = Path(__file__).resolve()
            # 获取提供者配置文件所在目录
            provider_path = current_path.parent
            # 构建provider.yaml文件的完整路径
            provider_yaml_file = provider_path / "providers.yaml"

            # 读取并解析YAML配置文件
            with provider_yaml_file.open(encoding="utf-8") as f:
                provider_configs = yaml.safe_load(f)

            # 遍历配置文件中的每个提供者配置
            for idx, provider_data in enumerate(provider_configs):
                # 创建ProviderEntity实例
                provider_entity = ProviderEntity(**provider_data)
                # 在映射字典中创建Provider对象，以提供者名称为键
                self.provider_map[provider_entity.name] = Provider(
                    name=provider_entity.name,
                    provider_entity=provider_entity,
                    position=idx + 1,
                )
        except FileNotFoundError:
            raise FileNotFoundError(provider_yaml_file) from None
        except yaml.YAMLError as e:
            error_msg = "Failed to parse provider configuration file"
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"Error loading provider configuration: {e!s}"
            logger.error(error_msg)  # 添加日志记录
            raise RuntimeError(error_msg) from e
