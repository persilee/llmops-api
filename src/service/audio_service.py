import base64
import json
import logging
import os
import urllib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import requests
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

    @classmethod
    def get_access_token(cls) -> str | None:
        """使用 AK，SK 生成鉴权签名（Access Token）

        :return: access_token，或是None(如果错误)
        """
        url = os.getenv("BAIDU_OAUTH_URL")
        params = {
            "grant_type": "client_credentials",
            "client_id": os.getenv("BAIDU_CLIENT_ID"),
            "client_secret": os.getenv("BAIDU_CLIENT_SECRET"),
        }

        return str(
            requests.post(url, params=params, timeout=30).json().get("access_token"),
        )

    @classmethod
    def get_file_content_as_base64(
        cls,
        file_obj: FileStorage | str,
        *,
        urlencoded: bool = False,
    ) -> str:
        """获取文件base64编码

        :param file_obj: 文件对象或文件路径
        :param urlencoded: 是否对结果进行urlencoded
        :return: base64编码信息
        """
        if isinstance(file_obj, str):
            # 如果是文件路径
            with Path(file_obj).open("rb") as f:
                content = base64.b64encode(f.read()).decode("utf8")
        else:
            # 如果是 FileStorage 对象
            content = base64.b64encode(file_obj.read()).decode("utf8")

        if urlencoded:
            content = urllib.parse.quote_plus(content)
        return content

    def audio_to_text(self, audio: FileStorage, account: Account) -> str:
        """将传递的语音转换成文本"""
        # 获取文件内容和字节数
        audio_content = audio.read()
        audio_bytes = len(audio_content)

        # 检查文件大小（可选）
        if audio_bytes > 10 * 1024 * 1024:  # 10MB
            error_msg = "文件大小超过限制"
            raise FailException(error_msg)

        # 重置文件指针
        audio.stream.seek(0)

        # 获取文件类型
        file_type = audio.mimetype
        if not file_type or not file_type.startswith("audio/"):
            error_msg = "不支持的文件类型"
            raise FailException(error_msg)

        # 指定的音频格式
        format_map = {
            "audio/wav": "wav",
            "audio/x-wav": "wav",  # WAV格式
            "audio/amr": "amr",  # AMR格式
            "audio/pcm": "pcm",  # PCM格式
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/x-m4a": "m4a",  # M4A格式
            "audio/mp4": "m4a",
        }
        format = format_map.get(file_type, "wav")

        speech = self.get_file_content_as_base64(audio)
        token = self.get_access_token()
        payload = json.dumps(
            {
                "format": format,
                "rate": 16000,
                "channel": 1,
                "cuid": str(account.id),
                "dev_pid": 80001,
                "speech": speech,
                "len": audio_bytes,
                "token": token,
            },
            ensure_ascii=False,
        )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = requests.request(
            "POST",
            os.getenv("BAIDU_BASE_URL"),
            headers=headers,
            data=payload.encode("utf-8"),
            timeout=30,
        )

        response.encoding = "utf-8"

        return response.json()["result"][0]

    def message_to_audio(self, message_id: UUID, account: Account) -> any:
        """将消息转换成语音"""
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
            voice = text_to_speech.get("voice", "echo")  # TODO: 暂时使用默认值
        elif message.invoke_from == InvokeFrom.SERVICE_API:
            error_msg = "开放API消息不支持文本转语音服务"
            raise NotFoundException(error_msg)

        # 5.根据状态获取不同的配置并判断是否开启文字转语音
        if enable is False:
            error_msg = "该应用未开启文字转语音功能，请核实后重试"
            raise FailException(error_msg)

        # 6.调用tts服务将消息answer转换成流式事件输出语音
        try:
            url = os.getenv("BAIDU_TEXT_TO_OAUTH_URL")
            token = self.get_access_token()
            params = {
                "tex": message.answer.strip(),
                "ctp": 1,
                "lan": "zh",
                "cuid": str(account.id),
                "spd": 5,
                "pit": 5,
                "vol": 5,
                "per": 1,
                "aue": 3,
                "tok": token,
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "cuid": str(account.id),
            }
            response = requests.get(
                url,
                params=params,
                stream=True,
                timeout=(5, 30),
                headers=headers,
            )
        except Exception as e:
            error_msg = "文字转语音失败，请稍后重试"
            log_msg = "文字转语音失败: %(error)s"
            logger.exception(log_msg)

            raise FailException(error_msg) from e

        return response

    @classmethod
    def _get_openai_client(cls) -> OpenAI:
        """获取OpenAI客户端"""
        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_API_BASE"),
        )
