from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from flask_login import current_user, login_required
from injector import inject

from pkg.response import success_json
from pkg.response.response import Response
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.service import AnalysisService


@inject
@dataclass
class AnalysisHandler:
    """统计分析处理器"""

    analysis_service: AnalysisService

    @route("/<uuid:app_id>", methods=["GET"])
    @swag_from(
        get_swagger_path("analysis_handler/get_app_analysis.yaml"),
    )
    @login_required
    def get_app_analysis(self, app_id: UUID) -> Response:
        """根据传递的应用id获取应用的统计信息"""
        app_analysis = self.analysis_service.get_app_analysis(app_id, current_user)
        return success_json(app_analysis)
