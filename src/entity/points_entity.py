from enum import Enum
from typing import ClassVar


class DeductFrom(str, Enum):
    """积分扣除来源"""

    OPTIMIZE = "optimize"  # 提示词优化
    WEB_APP = "web_app"  # web应用
    DEBUG = "debug"  # 智能体调试消息
    ASSISTANT_AGENT = "assistant_agent"  # 首页辅助Agent消息
    GENERATE_CONVERSATION = "generate_conversation"  # 会话名称生成


class DeductFromText:
    MAP: ClassVar[dict[DeductFrom, str]] = {
        DeductFrom.ASSISTANT_AGENT: "辅助智能体消息",
        DeductFrom.DEBUG: "智能体调试消息",
        DeductFrom.OPTIMIZE: "提示词优化",
        DeductFrom.GENERATE_CONVERSATION: "会话名称生成",
        DeductFrom.WEB_APP: "WEB应用消息",
    }
