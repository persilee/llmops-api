from pydantic import BaseModel


class ToolEntity(BaseModel):
    """工具实体类，用于定义工具的基本属性和参数。

    Attributes:
        name: 工具名称
        description: 工具描述信息
        label: 工具标签
        params: 工具参数列表，默认为空列表

    """

    name: str  # 工具名称
    description: str  # 工具描述信息
    label: str  # 工具标签
    params: list = []  # 工具参数列表，默认为空列表
