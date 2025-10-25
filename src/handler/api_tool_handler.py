from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from injector import inject

from pkg.response.response import (
    Response,
    success_json,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.api_tool_schema import (
    CreateApiToolReq,
    GetApiToolProviderResp,
    ValidateGetToolAPIProviderReq,
    ValidateOpenAPISchemaReq,
)
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

    @route("/create-api-tool", methods=["POST"])
    @swag_from(get_swagger_path("api_tool_handler/create_api_tool.yaml"))
    def create_api_tool(self) -> Response:
        """创建自定义API工具接口

        接收POST请求，根据传入的参数创建新的自定义API工具

        Returns:
            Response: 返回创建结果，成功时返回成功消息，失败时返回错误信息

        """
        req = CreateApiToolReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.create_api_tool(req)

        return success_message_json("自定义API工具创建成功")

    @route("/get-api-tool-provider/<provider_id>", methods=["GET"])
    @swag_from(get_swagger_path("api_tool_handler/get_api_tool_provider.yaml"))
    def get_api_tool_provider(self, provider_id: UUID) -> Response:
        """获取API工具提供者信息接口

        通过提供者ID获取对应的API工具提供者详细信息

        Args:
            provider_id (UUID): API工具提供者的唯一标识符

        Returns:
            Response: 返回获取结果，成功时返回提供者详细信息，失败时返回错误信息

        """
        req = ValidateGetToolAPIProviderReq(data={"provider_id": provider_id})
        if not req.validate():
            return validate_error_json(req.errors)

        api_tool_provider = self.api_tool_service.get_api_tool_provider(provider_id)

        resp = GetApiToolProviderResp()

        return success_json(resp.dump(api_tool_provider))
