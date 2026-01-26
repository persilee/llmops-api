from enum import Enum

# 生成icon描述提示词模板
GENERATE_ICON_PROMPT_TEMPLATE = """
你是一个拥有10年经验的AI绘画工程师，\
可以将用户传递的`应用名称`和`应用描述`转换为对应应用的icon描述。
该描述主要用于DallE AI绘画，并且该描述是英文，用户传递的数据如下:

应用名称: {name}。
应用描述: {description}。

并且除了icon描述提示词外，其他什么都不要生成
"""


class AppStatus(str, Enum):
    """应用状态枚举类"""

    DRAFT = "draft"
    PUBLISHED = "published"


class AppConfigType(str, Enum):
    """应用配置类型枚举类"""

    DRAFT = "draft"
    PUBLISHED = "published"


# 最大图片数
MAX_IMAGE_COUNT = 5
# 最大轮数
MAX_DIALOG_ROUNDS = 100
# 提示词最大长度
MAX_PRESET_PROMPT_LENGTH = 2000
# 工具最大长度
MAX_TOOL_COUNT = 5
# 知识库最大个数
MAX_DATASET_COUNT = 5
# 工作流最大个数
MAX_WORKFLOW_COUNT = 5
# 最大检索数量
MAX_RETRIEVAL_COUNT = 10
# 最大开场白长度
MAX_OPENING_STATEMENT_LENGTH = 2000
# 最大开场白问题个数
MAX_OPENING_QUESTIONS_COUNT = 3
# 最大关键词个数
MAX_REVIEW_KEYWORDS_COUNT = 100
# 应用默认配置信息
DEFAULT_APP_CONFIG = {
    "model_config": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "parameters": {
            "temperature": 0.5,
            "top_p": 0.85,
            "frequency_penalty": 0.2,
            "presence_penalty": 0.2,
            "max_tokens": 8192,
        },
    },
    "dialog_round": 3,
    "preset_prompt": "",
    "tools": [],
    "workflows": [],
    "datasets": [],
    "retrieval_config": {
        "retrieval_strategy": "semantic",
        "k": 10,
        "score": 0.5,
    },
    "long_term_memory": {
        "enable": False,
    },
    "opening_statement": "",
    "opening_questions": [],
    "suggested_after_answer": {
        "enable": True,
    },
    "speech_to_text": {
        "enable": False,
    },
    "text_to_speech": {
        "enable": False,
        "voice": "echo",
        "auto_play": False,
    },
    "review_config": {
        "enable": False,
        "keywords": [],
        "inputs_config": {
            "enable": False,
            "preset_response": "",
        },
        "outputs_config": {
            "enable": False,
        },
    },
}
