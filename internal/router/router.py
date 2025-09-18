from dataclasses import dataclass

from flask import Flask, Blueprint
from injector import inject

from internal.handler import AppHandler
from internal.router import register_with_class


@inject
@dataclass
class Router:
    """路由"""

    app_handler: AppHandler

    def register_route(self, app: Flask):
        """注册路由"""
        bp = Blueprint("llmops", __name__, url_prefix="")

        register_with_class(self.app_handler, bp, url_prefix="apps")

        app.register_blueprint(bp)
