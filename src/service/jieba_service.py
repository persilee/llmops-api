from dataclasses import dataclass

import jieba
import jieba.analyse
from injector import inject
from jieba.analyse import default_tfidf

from src.entity.jieba_entity import STOPWORD_SET


@inject
@dataclass
class JiebaService:
    """基于jieba分词库的关键词提取服务类。

    提供文本关键词提取功能，使用jieba的TF-IDF算法进行关键词分析。
    在初始化时会设置停用词集，以提高关键词提取的准确性。
    """

    def __init__(self) -> None:
        default_tfidf.stop_words = STOPWORD_SET

    @classmethod
    def extract_keywords(cls, text: str, max_keyword_pre_chunk: int = 10) -> list[str]:
        """使用jieba分词库从文本中提取关键词

        Args:
            text (str): 需要提取关键词的文本
            max_keyword_pre_chunk (int, optional): 每个文本块提取的最大关键词数量，
            默认为10

        Returns:
            list[str]: 返回提取的关键词列表，按重要性从高到低排序

        """
        return jieba.analyse.extract_tags(
            sentence=text,
            topK=max_keyword_pre_chunk,
        )
