from enum import Enum

DEFAULT_DATASET_DESCRIPTION_FORMATTER = (
    "当你需要回到管理《{name}》的时候可以引用该知识库"
)


class ProcessType(str, Enum):
    AUTOMATIC = "automatic"
    CUSTOM = "custom"


DEFAULT_PROCESS_RULE = {
    "mode": "custom",
    "rule": {
        "pre_process_rules": [
            {"id": "remove_extra_space", "enabled": True},
            {"id": "remove_url_and_email", "enabled": True},
        ],
        "segment": {
            "separators": [
                "\n\n",
                "\n",
                "。|！|？",
                r"\.\s|\!\s|\?\s",  # 英文标点符号后面通常需要加空格
                r"；|;\s",
                r"，|,\s",
                " ",
                "",
            ],
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
    },
}

KEYWORD_MAX_LENGTH = 10
MAX_UPLOAD_FILES = 10
EXPECTED_PRE_PROCESS_RULES_COUNT = 2
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 1000
MAX_CREATE_TOKEN = 1000


class DocumentStatus(str, Enum):
    """文档处理状态枚举类"""

    WAITING = "waiting"  # 等待处理
    PARSING = "parsing"  # 解析中
    SPLITTING = "splitting"  # 分割中
    INDEXING = "indexing"  # 索引中
    COMPLETED = "completed"  # 处理完成
    ERROR = "error"  # 处理出错


class SegmentStatus(str, Enum):
    """文档片段处理状态枚举类"""

    WAITING = "waiting"  # 等待处理
    INDEXING = "indexing"  # 索引中
    COMPLETED = "completed"  # 处理完成
    ERROR = "error"  # 处理出错


class RetrievalStrategy(str, Enum):
    """检索策略类型枚举"""

    FULL_TEXT = "full_text"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class RetrievalSource(str, Enum):
    """检索来源"""

    HIT_TESTING = "hit_testing"
    APP = "app"
