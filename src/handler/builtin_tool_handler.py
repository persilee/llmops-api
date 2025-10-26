import io
from dataclasses import dataclass

from flasgger import swag_from
from flask import send_file
from injector import inject

from pkg.response.response import Response, success_json
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.service.builtin_tool_service import BuiltinToolService


@inject
@dataclass
class BuiltinToolHandler:
    """内置工具处理器类

    用于处理获取内置工具列表和特定提供者工具的请求
    """

    builtin_tool_service: BuiltinToolService

    @route("", methods=["GET"])
    @swag_from(get_swagger_path("builtin_tool_handler/get_builtin_tools.yaml"))
    def get_builtin_tools(self) -> Response:
        """获取所有内置工具列表

        Returns:
            list: 内置工具列表

        """
        builtin_tools = self.builtin_tool_service.get_builtin_tools()

        return success_json(builtin_tools)

    @route(
        "/<string:provider_name>/tools/<string:tool_name>",
        methods=["GET"],
    )
    @swag_from(get_swagger_path("builtin_tool_handler/get_provider_tool.yaml"))
    def get_provider_tool(self, provider_name: str, tool_name: str) -> Response:
        """获取特定提供者的特定工具

        Args:
            provider_name (str): 提供者名称
            tool_name (str): 工具名称

        Returns:
            list: 特定工具的详细信息

        """
        builtin_tool = self.builtin_tool_service.get_builtin_tool(
            provider_name,
            tool_name,
        )

        return success_json(builtin_tool)

    @route("/<string:provider_name>/icon", methods=["GET"])
    @swag_from(get_swagger_path("builtin_tool_handler/get_provider_icon.yaml"))
    def get_provider_icon(self, provider_name: str) -> Response:
        """获取特定提供者的图标

        Args:
            provider_name (str): 提供者名称

        Returns:
            bytes: 图标数据

        """
        icon, mimetype = self.builtin_tool_service.get_provider_icon(provider_name)

        return send_file(io.BytesIO(icon), mimetype)

    @route("/categories", methods=["GET"])
    @swag_from(get_swagger_path("builtin_tool_handler/get_categories.yaml"))
    def get_categories(self) -> Response:
        """获取所有内置工具的分类

        Returns:
            list: 所有内置工具的分类

        """
        categories = self.builtin_tool_service.get_categories()

        return success_json(categories)
