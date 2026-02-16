import base64
import json
import logging
import os
import time
import urllib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import requests
from injector import inject
from openai import OpenAI
from redis import Redis
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
    redis_client: Redis

    def get_access_token(self) -> str | None:
        """使用 AK，SK 生成鉴权签名（Access Token）

        :return: access_token，或是None(如果错误)
        """
        # 尝试从 Redis 获取缓存的 token

        token = self.redis_client.get("baidu_access_token")
        if token:
            return token
        # 如果缓存中没有，请求新的 token
        url = os.getenv("BAIDU_OAUTH_URL")
        params = {
            "grant_type": "client_credentials",
            "client_id": os.getenv("BAIDU_CLIENT_ID"),
            "client_secret": os.getenv("BAIDU_CLIENT_SECRET"),
        }

        try:
            response = requests.post(url, params=params, timeout=30)
            token = response.json().get("access_token")
            if token:
                # 缓存 token 30 天
                self.redis_client.setex(
                    "baidu_access_token",
                    timedelta(days=30),
                    token,
                )
            else:
                return None
        except Exception:
            logger.exception(
                "获取 access_token 失败",
                extra={"url": url, "client_id": os.getenv("BAIDU_CLIENT_ID")},
            )
            return None

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

    def text_to_audio(self, text: str, voice: int, account: Account) -> any:
        try:
            url = os.getenv("BAIDU_TEXT_TO_OAUTH_URL")
            token = self.get_access_token()
            params = {
                "tex": text.strip(),
                "ctp": 1,
                "lan": "zh",
                "cuid": str(account.id),
                "spd": 5,
                "pit": 5,
                "vol": 5,
                "per": voice,
                "aue": 3,
                "tok": token,
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "cuid": str(account.id),
            }
            response = requests.request(
                "POST",
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

    def message_to_audio(self, message_id: UUID, account: Account) -> str:
        """将消息转换成语音"""
        try:
            # 验证消息和会话
            message = self._validate_message_and_conversation(message_id, account)

            # 验证应用配置
            enable, voice = self._validate_app_config(message, account)
            if not enable:
                self._handle_error("该应用未开启文字转语音功能，请核实后重试")

            # 创建任务并等待结果
            token = self.get_access_token()
            response = self._create_tts_task(message.answer.strip(), voice, token)
            result_url = self._wait_for_task_result(response["task_id"], token)

        except Exception as e:
            error_msg = "文字转语音失败，请稍后重试"
            log_msg = "文字转语音失败: %(error)s"
            logger.exception(log_msg)
            raise FailException(error_msg) from e

        return result_url

    def _wait_for_task_result(self, task_id: str, token: str) -> str:
        """等待任务完成并返回结果URL"""
        timeout = 300  # 5分钟超时
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                self._handle_error("任务处理超时")

            result = self._query_task(task_id, token)
            if not result:
                self._handle_error("查询任务状态失败：响应为空")

            # 检查任务状态
            task_info = result.get("tasks_info", [])
            if not task_info:
                self._handle_error("查询任务状态失败：缺少任务信息")
            task = task_info[0]
            status = task.get("task_status")
            if status == "Success":
                task_result = task.get("task_result", {})
                speech_url = task_result.get("speech_url")
                if not speech_url:
                    self._handle_error("获取语音URL失败：响应中缺少speech_url")
                return speech_url
            if status in ["Running", "Waiting"]:
                time.sleep(0.5)
                continue
            self._handle_error(f"语音转换失败：任务状态为 {status}")

    def _handle_error(self, error_msg: str) -> None:
        """统一处理错误信息"""
        raise FailException(error_msg)

    def _create_tts_task(self, text: str, voice: int, token: str) -> any:
        """创建文本转语音任务"""
        url = os.getenv("BAIDU_LONG_TEXT_TO_OAUTH_URL") + token
        payload = json.dumps(
            {
                "text": text,
                "lang": "zh",
                "format": "mp3-16k",
                "speed": 5,
                "pitch": 5,
                "volume": 5,
                "voice": voice,
                "enable_subtitle": 0,
            },
            ensure_ascii=False,
        )
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        response = requests.request(
            "POST",
            url,
            data=payload.encode("utf-8"),
            timeout=30,
            headers=headers,
        )

        return response.json()

    def _validate_message_and_conversation(
        self,
        message_id: UUID,
        account: Account,
    ) -> Message:
        """验证消息和会话的有效性"""
        message = self.get(Message, message_id)
        if (
            not message
            or message.is_deleted
            or message.answer.strip() == ""
            or message.created_by != account.id
        ):
            self._handle_error("该消息会话不存在，请核实后重试")

        conversation = message.conversation
        if (
            conversation is None
            or conversation.is_deleted
            or conversation.created_by != account.id
        ):
            error_msg = "该消息会话不存在，请核实后重试"
            raise NotFoundException(error_msg)

        return message

    def _validate_app_config(
        self,
        message: Message,
        account: Account,
    ) -> tuple[bool, int]:
        """验证应用配置并返回启用状态和音色"""
        if message.invoke_from in [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER]:
            app = self.get(App, message.conversation.app_id)
            if not app:
                self._handle_error("该消息会话归属应用不存在或校验失败，请核实后重试")
            if (
                message.invoke_from == InvokeFrom.DEBUGGER is True
                and app.account_id != account.id
            ):
                self._handle_error("该消息会话归属应用不存在或校验失败，请核实后重试")
            if (
                message.invoke_from == InvokeFrom.WEB_APP is False
                and app.status != AppStatus.PUBLISHED
            ):
                self._handle_error("该消息会话归属的应用未发布，请核实后重试")

            app_config: AppConfig | AppConfigVersion = (
                app.draft_app_config
                if message.invoke_from == InvokeFrom.DEBUGGER
                else app.app_config
            )
            text_to_speech = app_config.text_to_speech
            enable = text_to_speech.get("enable", False)
            voice = text_to_speech.get("voice", 4194)

        if message.invoke_from == InvokeFrom.SERVICE_API:
            self._handle_error("开放API消息不支持文本转语音服务")

        return enable, voice

    @classmethod
    def _get_openai_client(cls) -> OpenAI:
        """获取OpenAI客户端"""
        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_API_BASE"),
        )

    @classmethod
    def _query_task(cls, task_id: str, token: str) -> any:
        query_url = os.getenv("BAIDU_LONG_TEXT_TO_OAUTH_QUERY_URL") + token
        payload_query = json.dumps(
            {"task_ids": [task_id]},
            ensure_ascii=False,
        )
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.request(
            "POST",
            query_url,
            data=payload_query.encode("utf-8"),
            timeout=30,
            headers=headers,
        )

        return response.json()
