import base64
import json
import logging
import os
from collections.abc import Generator
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from injector import inject
from openai import OpenAI
from werkzeug.datastructures import FileStorage

from pkg.sqlalchemy import SQLAlchemy
from src.entity.app_entity import AppStatus
from src.entity.conversation_entity import InvokeFrom
from src.exception import FailException, NotFoundException
from src.model import Account, App, AppConfig, AppConfigVersion, Message
from src.service.app_service import AppService
from src.service.base_service import BaseService

logger = logging.getLogger(__name__)


@inject
@dataclass
class AudioService(BaseService):
    """语音服务，涵盖语音转文本、消息流式输出语音"""

    db: SQLAlchemy
    app_service: AppService

    def audio_to_text(self, audio: FileStorage) -> str:
        """将传递的语音转换成文本"""
        # 1.提取音频文件，并将音频文件转换成FileContent类型
        file_content = audio.stream.read()
        audio_file = BytesIO(file_content)
        audio_file.name = "recording.wav"

        # 2.创建OpenAI客户端，并调用whisper服务将音频转换成文字
        client = self._get_openai_client()
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )

        # 3.返回识别的文字内容
        return transcription.text

    def message_to_audio(self, message_id: UUID, account: Account) -> Generator:
        """将消息转换成流式时间输出语音"""
        # 1.根据传递的消息id获取消息并校验权限
        message = self.get(Message, message_id)
        if (
            not message
            or message.is_deleted
            or message.answer.strip() == ""
            or message.created_by != account.id
        ):
            error_msg = "该消息不存在，请核实后重试"
            raise NotFoundException(error_msg)

        # 2.校验消息归属的会话状态是否正常
        conversation = message.conversation
        if (
            conversation is None
            or conversation.is_deleted
            or conversation.created_by != account.id
        ):
            error_msg = "该消息会话不存在，请核实后重试"
            raise NotFoundException(error_msg)

        # 3.定义文本转语音启动配置、音色，默认为开启+echo音色
        enable = True
        voice = "echo"

        # 4.根据会话信息获取会话归属的应用
        if message.invoke_from in [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER]:
            app = self.get(App, conversation.app_id)
            if not app:
                error_msg = "该消息会话归属应用不存在或校验失败，请核实后重试"
                raise NotFoundException(error_msg)
            if (
                message.invoke_from == InvokeFrom.DEBUGGER is True
                and app.account_id != account.id
            ):
                error_msg = "该消息会话归属应用不存在或校验失败，请核实后重试"
                raise NotFoundException(error_msg)
            if (
                message.invoke_from == InvokeFrom.WEB_APP is False
                and app.status != AppStatus.PUBLISHED
            ):
                error_msg = "该消息会话归属的应用未发布，请核实后重试"
                raise NotFoundException(error_msg)

            app_config: AppConfig | AppConfigVersion = (
                app.draft_app_config
                if message.invoke_from == InvokeFrom.DEBUGGER
                else app.app_config
            )
            text_to_speech = app_config.text_to_speech
            enable = text_to_speech.get("enable", False)
            voice = text_to_speech.get("voice", "echo")
        elif message.invoke_from == InvokeFrom.SERVICE_API:
            error_msg = "开放API消息不支持文本转语音服务"
            raise NotFoundException(error_msg)

        # 5.根据状态获取不同的配置并判断是否开启文字转语音
        if enable is False:
            error_msg = "该应用未开启文字转语音功能，请核实后重试"
            raise FailException(error_msg)

        # 6.调用tts服务将消息answer转换成流式事件输出语音
        try:
            client = self._get_openai_client()
            response = client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=voice,
                response_format="mp3",
                input=message.answer.strip(),
            )
        except Exception as e:
            error_msg = "文字转语音失败，请稍后重试"
            log_msg = "文字转语音失败: %(error)s"
            logger.exception(log_msg)

            raise FailException(error_msg) from e

        # 6.定义内部函数实现流式事件输出
        def tts() -> Generator:
            """内部函数，从response中获取音频流式事件输出数据"""
            common_data = {
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "audio": "",
            }
            for chunk in response.__enter__().iter_bytes(1024):
                data = {**common_data, "audio": base64.b64encode(chunk).decode("utf-8")}
                yield f"event: tts_message\ndata: {json.dumps(data)}\n\n"
            yield f"event: tts_end\ndata: {json.dumps(common_data)}\n\n"

        # 7.调用tts函数流式事件输出语音数据
        return tts()

    @classmethod
    def _get_openai_client(cls) -> OpenAI:
        """获取OpenAI客户端"""
        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_API_BASE"),
        )
