from pydantic import BaseModel, Field


class ToolEntity(BaseModel):
    """API工具实体类，用于定义API工具的基本信息和配置"""

    id: str = Field(default="", description="API提供者的唯一标识符")
    name: str = Field(default="", description="API提供者的显示名称")
    url: str = Field(
        default="",
        description="API提供者的完整请求URL地址，包含协议和域名",
    )
    method: str = Field(
        default="get",
        description="HTTP请求方法，如get、post、put、delete等",
    )
    description: str = Field(
        default="",
        description="API功能的详细描述，用于说明API的用途和效果",
    )
    headers: list[dict] = Field(
        default_factory=list,
        description="HTTP请求头列表，每个元素为包含键值对的字典",
    )
    parameters: list[dict] = Field(
        default_factory=list,
        description="API请求参数列表，每个参数为包含名称、类型、是否必需等信息的字典",
    )
