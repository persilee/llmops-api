from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from src.core.tools.builtin_tools.entities.tool_entity import ToolEntity
from src.lib.helper import dynamic_import


class ProviderEntity(BaseModel):
    """提供者实体类，用于存储提供者的基本信息。

    包含提供者的名称、描述、标签、图标、背景色和类别等属性。
    """

    name: str  # 提供者名称
    description: str  # 提供者描述信息
    label: str  # 提供者标签
    icon: str  # 提供者图标
    background: str  # 提供者背景色
    category: str  # 提供者类别
    created_at: int = 0  # 提供者创建时间


class Provider(BaseModel):
    """提供者类，用于存储提供者的实例信息。

    包含提供者的实例名称、位置信息、实体信息和工具函数映射等属性。
    """

    name: str  # 提供者实例名称
    position: int  # 提供者位置信息
    provider_entity: ProviderEntity  # 提供者实体信息
    tool_func_map: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )  # 工具函数映射字典，用于存储工具名称与对应函数的映射关系
    tool_entity_map: dict[
        str,
        ToolEntity,
    ] = Field(
        default_factory=dict,
    )  # 工具实体映射字典，用于存储工具名称与对应工具实体的映射关系

    def __init__(self, **kwargs: dict[str, Any]) -> None:
        """初始化Provider实例。

        Args:
            **kwargs: 提供者的初始化参数，包括name、position、provider_entity等属性

        """
        super().__init__(**kwargs)
        self._provider_init()  # 调用提供者初始化方法，加载工具配置和函数

    def get_tool(self, tool_name: str) -> Any:
        """获取指定名称的工具函数。

        Args:
            tool_name (str): 工具名称

        Returns:
            Any: 工具函数对象，如果不存在则返回None

        """
        return self.tool_func_map.get(tool_name, None)

    def get_tool_entity(self, tool_name: str) -> ToolEntity:
        """获取指定名称的工具实体。

        Args:
            tool_name (str): 工具名称

        Returns:
            ToolEntity: 工具实体对象，如果不存在则返回None

        """
        return self.tool_entity_map.get(tool_name, None)

    def get_tool_entities(self) -> list[ToolEntity]:
        """获取所有工具实体的列表。

        Returns:
            list[ToolEntity]: 包含所有工具实体的列表

        """
        return list(self.tool_entity_map.values())

    def _provider_init(self) -> None:
        """初始化提供者的工具配置和函数映射。

        Raises:
            FileNotFoundError: 当配置文件不存在时
            yaml.YAMLError: 当YAML文件格式错误时
            ImportError: 当工具函数导入失败时

        """
        try:
            # 获取当前文件的绝对路径
            current_path = Path(__file__).resolve()
            # 获取entities目录路径
            entities_path = current_path.parent
            # 构建provider目录路径
            provider_path = entities_path.parent / "providers" / self.name

            # 构建positions.yaml文件路径
            positions_yaml_path = provider_path / "positions.yaml"

            # 读取positions.yaml文件内容
            with positions_yaml_path.open(encoding="utf-8") as f:
                positions_yaml_data = yaml.safe_load(f)

            # 遍历positions.yaml中的每个工具名称
            for tool_name in positions_yaml_data:
                try:
                    # 构建工具配置文件路径
                    tool_yaml_path = provider_path / f"{tool_name}.yaml"
                    # 读取工具配置文件
                    with tool_yaml_path.open(encoding="utf-8") as f:
                        tool_yaml_data = yaml.safe_load(f)

                    # 创建工具实体并添加到映射字典
                    self.tool_entity_map[tool_name] = ToolEntity(**tool_yaml_data)

                    # 动态导入工具函数并添加到映射字典
                    self.tool_func_map[tool_name] = dynamic_import(
                        f"src.core.tools.builtin_tools.providers.{self.name}",
                        tool_name,
                    )
                except (FileNotFoundError, yaml.YAMLError, ImportError) as e:
                    print(f"Error loading tool {tool_name}: {e!s}")
                    continue
        except Exception as e:
            print(f"Error initializing provider {self.name}: {e!s}")
            raise
