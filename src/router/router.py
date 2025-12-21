from dataclasses import dataclass

from flask import Blueprint, Flask
from injector import inject

from src.handler import AppHandler, BuiltinToolHandler
from src.handler.account_handler import AccountHandler
from src.handler.ai_handler import AIHandler
from src.handler.api_key_handler import ApiKeyHandler
from src.handler.api_tool_handler import ApiToolHandler
from src.handler.auth_handler import AuthHandler
from src.handler.dataset_handler import DatasetHandler
from src.handler.document_handler import DocumentHandler
from src.handler.oauth_handler import OAuthHandler
from src.handler.segment_handler import SegmentHandler
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
    segment_handler: SegmentHandler
    oauth_handler: OAuthHandler
    account_handler: AccountHandler
    auth_handler: AuthHandler
    ai_handler: AIHandler
    api_key_handler: ApiKeyHandler

    def register_route(self, app: Flask) -> None:
        """注册路由"""
        bp = Blueprint("llmops", __name__, url_prefix="")

        register_with_class(self.app_handler, bp, url_prefix="apps")
        register_with_class(self.builtin_tool_handler, bp, url_prefix="builtin-tools")
        register_with_class(self.api_tool_handler, bp, url_prefix="api-tools")
        register_with_class(self.upload_file_handler, bp, url_prefix="upload-files")
        register_with_class(self.dataset_handler, bp, url_prefix="datasets")
        register_with_class(self.document_handler, bp, url_prefix="datasets")
        register_with_class(self.segment_handler, bp, url_prefix="datasets")
        register_with_class(self.oauth_handler, bp, url_prefix="oauth")
        register_with_class(self.account_handler, bp, url_prefix="account")
        register_with_class(self.auth_handler, bp, url_prefix="auth")
        register_with_class(self.ai_handler, bp, url_prefix="ai")
        register_with_class(self.api_key_handler, bp, url_prefix="api-keys")

        app.register_blueprint(bp)
