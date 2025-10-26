from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from flask import request
from injector import inject

from pkg.paginator.paginator import PageModel
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
    GetApiToolProvidersWithPageReq,
    GetApiToolProvidersWithPageResp,
    GetApiToolResp,
    UpdateApiToolProviderReq,
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

    @route("/create-api-tool-provider", methods=["POST"])
    @swag_from(get_swagger_path("api_tool_handler/create_api_tool_provider.yaml"))
    def create_api_tool_provider(self) -> Response:
        """创建自定义API工具接口

        接收POST请求，根据传入的参数创建新的自定义API工具

        Returns:
            Response: 返回创建结果，成功时返回成功消息，失败时返回错误信息

        """
        req = CreateApiToolReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.create_api_tool_provider(req)

        return success_message_json("自定义API工具创建成功")

    @route("/get-api-tool-provider/<uuid:provider_id>", methods=["GET"])
    @swag_from(get_swagger_path("api_tool_handler/get_api_tool_provider.yaml"))
    def get_api_tool_provider(self, provider_id: UUID) -> Response:
        """获取API工具提供者信息接口

        通过提供者ID获取对应的API工具提供者详细信息

        Args:
            provider_id (UUID): API工具提供者的唯一标识符

        Returns:
            Response: 返回获取结果，成功时返回提供者详细信息，失败时返回错误信息

        """
        api_tool_provider = self.api_tool_service.get_api_tool_provider(provider_id)

        resp = GetApiToolProviderResp()

        return success_json(resp.dump(api_tool_provider))

    @route("/get-api-tool/<uuid:provider_id>/tools/<string:tool_name>", methods=["GET"])
    @swag_from(get_swagger_path("api_tool_handler/get_api_tool.yaml"))
    def get_api_tool(self, provider_id: UUID, tool_name: str) -> Response:
        """获取API工具信息接口

        通过提供者ID和工具名称获取对应的API工具详细信息

        Args:
            provider_id (UUID): API工具提供者的唯一标识符
            tool_name (str): API工具的名称

        Returns:
            Response: 返回获取结果，成功时返回工具详细信息，失败时返回错误信息

        """
        api_tool = self.api_tool_service.get_api_tool(provider_id, tool_name)

        resp = GetApiToolResp()

        return success_json(resp.dump(api_tool))

    @route("/<uuid:provider_id>/delete", methods=["POST"])
    @swag_from(get_swagger_path("api_tool_handler/delete_api_tool_provider.yaml"))
    def delete_api_tool_provider(self, provider_id: UUID) -> Response:
        """删除API工具提供者接口

        通过提供者ID删除对应的API工具提供者

        Args:
            provider_id (UUID): API工具提供者的唯一标识符

        Returns:
            Response: 返回删除结果，成功时返回成功信息，失败时返回错误信息

        """
        self.api_tool_service.delete_api_tool_provider(provider_id)

        return success_message_json("删除自定义 API 插件成功")

    @route("", methods=["GET"])
    @swag_from(
        get_swagger_path("api_tool_handler/get_api_tool_providers_with_page.yaml"),
    )
    def get_api_tool_providers_with_page(self) -> Response:
        """分页获取API工具提供者列表。

        通过请求参数进行分页查询，返回API工具提供者列表和分页信息。

        Returns:
            Response: 包含分页数据和分页信息的响应对象
                - 成功时返回分页的API工具提供者列表数据
                - 验证失败时返回验证错误信息

        """
        # 从请求参数中创建分页查询请求对象
        req = GetApiToolProvidersWithPageReq(request.args)
        # 验证请求数据是否符合要求
        if not req.validate():
            # 如果验证失败，返回验证错误信息
            return validate_error_json(req.errors)

        # 调用服务层方法，获取API工具提供者列表和分页器
        api_tool_providers, paginator = (
            self.api_tool_service.get_api_tool_providers_with_page(req)
        )

        # 创建响应对象，设置many=True表示处理多个对象
        resp = GetApiToolProvidersWithPageResp(many=True)

        # 返回成功响应，包含分页数据和分页信息
        return success_json(
            PageModel(list=resp.dump(api_tool_providers), paginator=paginator),
        )

    @route("/<uuid:provider_id>", methods=["POST"])
    @swag_from(get_swagger_path("api_tool_handler/update_api_tool_provider.yaml"))
    def update_api_tool_provider(self, provider_id: UUID) -> Response:
        """更新API工具提供者信息

        Args:
            provider_id (UUID): API工具提供者的唯一标识符

        Returns:
            Response: 更新操作的响应结果，成功时返回成功消息

        """
        # 创建更新请求对象
        req = UpdateApiToolProviderReq()
        # 验证请求数据
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用服务层执行更新操作
        self.api_tool_service.update_api_tool_provider(provider_id, req)

        # 返回成功响应
        return success_message_json("更新成功")
