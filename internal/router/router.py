from flask import Flask, Blueprint

from internal.handler import app_handler


class Router:
    """路由"""

    @staticmethod
    def register_route(app: Flask):
        """注册路由"""
        bp = Blueprint("llmops", __name__, url_prefix="")

        app_handler.api.register(bp, url_prefix="/app")

        app.register_blueprint(bp)
