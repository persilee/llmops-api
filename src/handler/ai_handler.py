from dataclasses import dataclass

from flasgger import swag_from
from flask_login import current_user, login_required
from injector import inject

from pkg.response.response import (
    Response,
    compact_generate_response,
    success_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.ai_schema import GenerateSuggestedQuestionsReq, OptimizePromptReq
from src.service.ai_service import AIService


@inject
@dataclass
class AIHandler:
    ai_service: AIService

    @route("/optimize/prompt", methods=["POST"])
    @swag_from(
        get_swagger_path("ai_handler/optimize_prompt.yaml"),
    )
    @login_required
    def optimize_prompt(self) -> Response:
        """优化提示词的API端点处理函数

        接收用户输入的提示词，通过AI服务进行优化处理

        Returns:
            Response: 包含优化后提示词的响应对象

        """
        # 创建请求对象并验证输入
        req = OptimizePromptReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用AI服务优化提示词
        resp = self.ai_service.optimize_prompt(req.prompt.data)

        # 返回优化后的结果
        return compact_generate_response(resp)

    @route("/suggested/questions", methods=["POST"])
    @swag_from(
        get_swagger_path("ai_handler/generate_suggested_questions.yaml"),
    )
    @login_required
    def generate_suggested_questions(self) -> Response:
        """生成建议问题的API端点处理函数

        根据给定的消息ID生成相关的建议问题列表

        Returns:
            Response: 包含建议问题列表的响应对象

        """
        req = GenerateSuggestedQuestionsReq()
        if not req.validate():
            return validate_error_json(req.errors)

        suggested_questions = (
            self.ai_service.generate_suggested_questions_from_message_id(
                req.message_id.data,
                current_user,
            )
        )

        return success_json(suggested_questions)
