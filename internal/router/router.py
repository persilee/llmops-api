from dataclasses import dataclass

from flask import Flask, Blueprint
from injector import inject

from internal.handler import AppHandler


@inject
@dataclass
class Router:
    """路由"""
    app_handler: AppHandler

    def register_route(self, app: Flask):
        """注册路由"""
        bp = Blueprint("llmops", __name__, url_prefix="")
        bp.add_url_rule("/completion", methods=["POST"],
                        view_func=self.app_handler.completion)
        bp.add_url_rule("/app", methods=["POST"],
                        view_func=self.app_handler.create_app)
        bp.add_url_rule("/app/<uuid:app_id>", methods=["GET"],
                        view_func=self.app_handler.get_app)
        bp.add_url_rule("/app/<uuid:app_id>", methods=["POST"],
                        view_func=self.app_handler.update_app)
        bp.add_url_rule("/app/<uuid:app_id>/delete", methods=["POST"],
                        view_func=self.app_handler.delete_app)

        app.register_blueprint(bp)
