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
from src.schemas.ai_schema import (
    GenerateConversationNameReq,
    GenerateSuggestedQuestionsReq,
    OptimizePromptReq,
)
from src.service.ai_service import AIService


@inject
@dataclass
class AIHandler:
    ai_service: AIService

    @route("/generate-conversation-name", methods=["POST"])
    @swag_from(
        get_swagger_path("ai_handler/generate_conversation_name.yaml"),
    )
    @login_required
    def generate_conversation_name(self) -> Response:
        """生成对话名称的API端点处理函数

        接收用户输入的对话内容，通过AI服务生成合适的对话名称

        Args:
            query (str): 用户输入的对话内容

        Returns:
            Response: 包含生成的对话名称的响应对象

        """
        # 创建请求对象并验证输入
        req = GenerateConversationNameReq()

        # 验证请求数据是否合法
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用AI服务生成对话名称
        name = self.ai_service.generate_conversation_name(req.query.data)

        # 返回包含生成名称的成功响应
        return success_json({"name": name})

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
