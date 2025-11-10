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
