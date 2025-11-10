from dataclasses import dataclass

from flask import Blueprint, Flask
from injector import inject

from src.handler import AppHandler, BuiltinToolHandler
from src.handler.api_tool_handler import ApiToolHandler
from src.handler.dataset_handler import DatasetHandler
from src.handler.document_handler import DocumentHandler
from src.handler.upload_file_handler import UploadFileHandler
from src.router import register_with_class


@inject
@dataclass
class Router:
    """路由"""

    app_handler: AppHandler
    builtin_tool_handler: BuiltinToolHandler
    api_tool_handler: ApiToolHandler
    upload_file_handler: UploadFileHandler
    dataset_handler: DatasetHandler
    document_handler: DocumentHandler

    def register_route(self, app: Flask) -> None:
        """注册路由"""
        bp = Blueprint("llmops", __name__, url_prefix="")

        register_with_class(self.app_handler, bp, url_prefix="apps")
        register_with_class(self.builtin_tool_handler, bp, url_prefix="builtin-tools")
        register_with_class(self.api_tool_handler, bp, url_prefix="api-tools")
        register_with_class(self.upload_file_handler, bp, url_prefix="upload-files")
        register_with_class(self.dataset_handler, bp, url_prefix="datasets")
        register_with_class(self.document_handler, bp, url_prefix="datasets")

        app.register_blueprint(bp)
