from dataclasses import dataclass

from flask import Blueprint, Flask
from injector import inject

from src.handler import AppHandler
from src.router import register_with_class


@inject
@dataclass
class Router:
    """路由"""

    app_handler: AppHandler

    def register_route(self, app: Flask) -> None:
        """注册路由"""
        bp = Blueprint("llmops", __name__, url_prefix="")

        register_with_class(self.app_handler, bp, url_prefix="apps")

        app.register_blueprint(bp)
