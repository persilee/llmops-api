from dataclasses import dataclass

import jieba
import jieba.analyse
from injector import inject
from jieba.analyse import default_tfidf

from src.entity.jieba_entity import STOPWORD_SET


@inject
@dataclass
class JiebaService:
    def __init__(self) -> None:
        default_tfidf.stop_words = STOPWORD_SET

    @classmethod
    def extract_keywords(cls, text: str, max_keyword_pre_chunk: int = 10) -> list[str]:
        return jieba.analyse.extract_tags(
            sentence=text,
            topK=max_keyword_pre_chunk,
        )
