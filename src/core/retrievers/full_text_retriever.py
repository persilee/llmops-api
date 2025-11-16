from collections import Counter
from uuid import UUID

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.model.dataset import KeywordTable, Segment
from src.service.jieba_service import JiebaService


class FullTextRetriever(BaseRetriever):
    db: SQLAlchemy
    jieba_service: JiebaService
    dataset_ids: list[UUID]
    search_kwargs: dict = Field(default_factory=dict)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[LCDocument]:
        """根据查询文本检索相关文档片段。

        Args:
            query: 查询文本字符串
            run_manager: 回调管理器，用于管理检索过程中的回调

        Returns:
            list[LCDocument]: 包含相关文档片段的LangChain文档对象列表，
            每个文档对象包含：
                - page_content: 文档内容
                - metadata: 文档元数据，包括账户ID、数据集ID、文档ID等信息

        该方法执行以下步骤：
        1. 使用jieba服务从查询中提取关键词
        2. 从数据库中获取关键词表并匹配相关文档片段ID
        3. 统计文档片段ID的出现频率并排序
        4. 从数据库查询对应的文档片段
        5. 构建并返回格式化的文档对象列表

        """
        # 使用jieba服务从查询中提取最多10个关键词
        keywords = self.jieba_service.extract_keywords(query, 10)

        # 从数据库中获取所有相关的关键词表
        keyword_tables = [
            keyword_table
            for (keyword_table,) in self.db.session.query(KeywordTable)
            .with_entities(
                KeywordTable.keyword_table,  # 只查询关键词表字段
            )
            .filter(
                KeywordTable.dataset_id.in_(
                    self.dataset_ids,
                ),  # 筛选指定数据集的关键词表
            )
            .all()
        ]

        all_ids = []  # 存储所有匹配的文档片段ID
        # 遍历所有关键词表，查找匹配的关键词
        for keyword_table in keyword_tables:
            for keyword, segment_ids in keyword_table.items():
                if keyword in keywords:  # 如果关键词在提取的关键词列表中
                    all_ids.extend(segment_ids)  # 添加对应的文档片段ID

        # 使用Counter统计每个文档片段ID出现的频率
        id_counter = Counter(all_ids)

        # 获取要返回的文档数量，默认为4
        k = self.search_kwargs.get("k", 4)
        # 获取出现频率最高的k个文档片段ID
        top_10_ids = id_counter.most_common(k)

        # 从数据库查询对应的文档片段
        segments = (
            self.db.session.query(Segment)
            .filter(
                Segment.id.in_(
                    [id for id, _ in top_10_ids],
                ),  # 筛选ID在top_10_ids中的文档片段
            )
            .all()
        )
        # 创建ID到文档片段的映射字典
        segment_dict = {str(segment.id): segment for segment in segments}

        # 按照关键词匹配频率对文档片段进行排序
        sorted_segments = [
            segment_dict[str(id)] for id, freq in top_10_ids if id in segment_dict
        ]

        # 构建并返回LangChain文档对象列表
        return [
            LCDocument(
                page_content=segment.content,  # 文档内容
                metadata={  # 文档元数据
                    "account_id": str(segment.account_id),  # 账户ID
                    "dataset_id": str(segment.dataset_id),  # 数据集ID
                    "document_id": str(segment.document_id),  # 文档ID
                    "segment_id": str(segment.id),  # 文档片段ID
                    "node_id": str(segment.node_id),  # 节点ID
                    "document_enabled": True,  # 文档启用状态
                    "segment_enabled": True,  # 文档片段启用状态
                    "score": 0,  # 相关性分数
                },
            )
            for segment in sorted_segments  # 遍历排序后的文档片段列表
        ]
