from pydantic import BaseModel, field_validator


class CategoryEntity(BaseModel):
    """分类实体类，用于存储工具分类的基本信息"""

    category: str  # 分类名称
    name: str  # 工具名称
    icon: str  # 图标标识

    @field_validator("icon")
    def check_icon_extension(cls, v: str) -> str:  # noqa: N805
        """检查图标文件扩展名"""
        if not v.endswith(".svg"):
            error_msg = "图标文件必须以.svg结尾"
            raise ValueError(error_msg)
        return v
