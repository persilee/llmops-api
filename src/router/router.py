from dataclasses import dataclass

from flask import Blueprint, Flask
from injector import inject

from src.handler import AppHandler, BuiltinToolHandler
from src.handler.api_tool_handler import ApiToolHandler
from src.router import register_with_class


@inject
@dataclass
class Router:
    """路由"""

    app_handler: AppHandler
    builtin_tool_handler: BuiltinToolHandler
    api_tool_handler: ApiToolHandler

    def register_route(self, app: Flask) -> None:
        """注册路由"""
        bp = Blueprint("llmops", __name__, url_prefix="")

        register_with_class(self.app_handler, bp, url_prefix="apps")
        register_with_class(self.builtin_tool_handler, bp, url_prefix="builtin-tools")
        register_with_class(self.api_tool_handler, bp, url_prefix="api-tools")

        app.register_blueprint(bp)
