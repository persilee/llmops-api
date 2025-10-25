from dataclasses import dataclass

from flasgger import swag_from
from injector import inject

from pkg.response.response import (
    Response,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.api_tool_schema import ValidateOpenAPISchemaReq
from src.service.api_tool_service import ApiToolService


@inject
@dataclass
class ApiToolHandler:
    """API工具处理器类

    用于处理与API工具相关的HTTP请求
    """

    api_tool_service: ApiToolService

    @route("/validate-openapi-schema", methods=["POST"])
    @swag_from(get_swagger_path("api_tool_handler/validate_openapi_schema.yaml"))
    def validate_openapi_schema(self) -> Response:
        """验证OpenAPI模式接口

        接收POST请求，验证传入的OpenAPI模式是否符合规范

        Returns:
            Response: 返回验证结果，成功时返回成功消息，失败时返回错误信息

        """
        # 创建请求对象
        req = ValidateOpenAPISchemaReq()
        # 验证请求数据
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用服务层解析OpenAPI数据
        self.api_tool_service.parse_openapi_schema(req.openapi_schema.data)

        # 返回成功响应
        return success_message_json("数据效验成功")
