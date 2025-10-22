from pathlib import Path
from typing import Any

import yaml
from injector import inject, singleton
from pydantic import BaseModel, Field

from src.core.tools.builtin_tools.entities.category_entity import CategoryEntity


@inject
@singleton
class BuiltinCategoryManager(BaseModel):
    """内置分类管理器类，用于管理和加载系统内置的分类信息。

    属性:
        category_map (dict[str, Any]): 存储分类信息的字典，键为分类名称，
        值为包含分类实体和图标的字典
    """

    category_map: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **kwargs: Any) -> None:
        """初始化方法，调用父类初始化方法后，自动执行分类的初始化。

        参数:
            **kwargs: 传递给父类构造函数的参数
        """
        super().__init__(**kwargs)
        self._init_categories()

    def get_category_map(self) -> dict[str, Any]:
        """获取分类映射字典的方法。

        返回:
            dict[str, Any]: 包含所有分类信息的字典
        """
        return self.category_map

    def _init_categories(self) -> None:
        # 如果分类映射已经存在，直接返回，避免重复初始化
        if self.category_map:
            return

        # 获取当前文件所在目录路径
        current_path = Path(__file__).parent
        # 构建categories.yaml文件的完整路径
        category_yaml_path = current_path / "categories.yaml"
        # 打开并读取YAML配置文件
        with category_yaml_path.open("r") as f:
            categories = yaml.safe_load(f)

        # 遍历所有分类配置
        for category in categories:
            # 将配置转换为CategoryEntity对象
            category_entity = CategoryEntity(**category)

            # 构建图标文件的完整路径
            icon_path = current_path / "icons" / category_entity.icon
            # 检查图标文件是否存在
            if not icon_path.exists():
                error_msg = f"该分类{category_entity.category}的图标不存在"
                raise FileNotFoundError(error_msg)

            # 读取图标文件内容
            with icon_path.open(encoding="utf-8") as f:
                icon = f.read()

            # 将分类实体和图标内容存储到分类映射中
            self.category_map[category_entity.category] = {
                "entity": category_entity,
                "icon": icon,
            }
