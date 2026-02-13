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
from src.schemas.audio_schema import AudioToTextReq, MessageToAudioReq
from src.service.audio_service import AudioService


@inject
@dataclass
class AudioHandler:
    audio_service: AudioService

    @route("/text", methods=["POST"])
    @swag_from(get_swagger_path("audio_handler/audio_to_text.yaml"))
    @login_required
    def audio_to_text(self) -> Response:
        """将语音转换成文本"""
        # 1.提取请求并校验
        req = AudioToTextReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务将音频文件转换成文本
        text = self.audio_service.audio_to_text(req.file.data, current_user)

        return success_json({"text": text})

    @route("", methods=["POST"])
    @swag_from(get_swagger_path("audio_handler/message_to_audio.yaml"))
    @login_required
    def message_to_audio(self) -> Response:
        """将消息转换成流式输出音频"""
        # 1.提取请求并校验
        req = MessageToAudioReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取流式事件输出
        response = self.audio_service.message_to_audio(
            req.message_id.data,
            current_user,
        )

        return compact_generate_response(response)
