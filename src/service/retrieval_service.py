from dataclasses import dataclass
from uuid import UUID

from injector import inject
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document as LCDocument
from sqlalchemy import update

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.entity.dataset_entity import RetrievalSource, RetrievalStrategy
from src.exception.exception import NotFoundException
from src.model.account import Account
from src.model.dataset import Dataset, DatasetQuery, Segment
from src.service.base_service import BaseService
from src.service.jieba_service import JiebaService
from src.service.vector_database_service import VectorDatabaseService


@inject
@dataclass
class RetrievalService(BaseService):
    db: SQLAlchemy
    jieba_service: JiebaService
    vector_database_service: VectorDatabaseService

    def search_in_datasets(
        self,
        dataset_ids: list[UUID],
        account: Account,
        query: str,
        retrieval_strategy: str = RetrievalStrategy.SEMANTIC,
        retrieval_source: str = RetrievalSource.HIT_TESTING,
        **kwargs: dict,
    ) -> list[LCDocument]:
        """在指定的知识库中执行搜索查询。

        Args:
            dataset_ids (list[UUID]): 要搜索的知识库ID列表
            account (Account): 当前用户账户
            query (str): 搜索查询字符串
            retrieval_strategy (str, optional): 检索策略，默认为语义检索(SEMANTIC)。
                可选值包括：
                - SEMANTIC: 语义检索
                - FULL_TEXT: 全文检索
                - HYBRID: 混合检索
            retrieval_source (str, optional): 检索来源标识，默认为HIT_TESTING
            **kwargs: 额外的检索参数，包括：
                - k (int): 返回结果数量，默认为4
                - score (float): 相似度阈值，默认为0

        Returns:
            list[LCDocument]: 检索到的文档列表，每个文档包含内容和元数据

        Raises:
            NotFoundException: 当指定的知识库ID不存在时抛出

        Note:
            该方法会自动记录查询历史并更新文档段的命中次数。
            混合检索时，语义检索和全文检索的权重各占50%。

        """
        k = kwargs.get("k", 4)  # 获取返回结果数量，默认为4
        score = kwargs.get("score", 0)  # 获取相似度阈值，默认为0
        # 查询指定ID且属于当前账户的知识库
        datasets = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(dataset_ids),
                Dataset.account_id == account.id,
            )
            .all()
        )
        # 检查是否找到知识库
        if datasets is None or len(datasets) == 0:
            error_msg = f"没有找到ID为{dataset_ids}的知识库"
            raise NotFoundException(error_msg)

        # 提取有效的知识库ID列表
        dataset_ids = [dataset.id for dataset in datasets]

        from src.core.retrievers.full_text_retriever import FullTextRetriever
        from src.core.retrievers.semantic_retriever import SemanticRetriever

        # 创建语义检索器，用于基于向量相似度的检索
        semantic_retriever = SemanticRetriever(
            dataset_ids=dataset_ids,
            vector_store=self.vector_database_service.vector_store,
            search_kwargs={
                "k": k,
                "score_threshold": score,
            },
        )
        # 创建全文检索器，用于基于关键词匹配的检索
        full_text_retriever = FullTextRetriever(
            db=self.db,
            dataset_ids=dataset_ids,
            jieba_service=self.jieba_service,
            search_kwargs={
                "k": k,
            },
        )
        # 创建混合检索器，结合语义和全文检索的结果
        hybrid_retriever = EnsembleRetriever(
            retrievers=[semantic_retriever, full_text_retriever],
            weights=[0.5, 0.5],  # 语义和全文检索的权重各占50%
        )

        # 根据检索策略选择合适的检索器执行查询
        if retrieval_strategy == RetrievalStrategy.SEMANTIC:
            lc_documents = semantic_retriever.invoke(query)[:k]  # 语义检索
        elif retrieval_strategy == RetrievalStrategy.FULL_TEXT:
            lc_documents = full_text_retriever.invoke(query)[:k]  # 全文检索
        else:
            lc_documents = hybrid_retriever.invoke(query)[:k]  # 混合检索

        # 记录每次查询的历史信息
        unique_dataset_ids = list(
            {str(lc_document.metadata["dataset_id"]) for lc_document in lc_documents},
        )
        for dataset_id in unique_dataset_ids:
            self.create(
                DatasetQuery,
                dataset_id=dataset_id,
                query=query,
                source=retrieval_source,
                source_app_id=None,
                created_by=account.id,
            )

        # 更新检索到的文档段的命中次数
        with self.db.auto_commit():
            stmt = (
                update(Segment)
                .where(
                    Segment.id.in_(
                        [
                            lc_document.metadata["segment_id"]
                            for lc_document in lc_documents
                        ],
                    ),
                )
                .values(
                    hit_count=Segment.hit_count + 1,  # 命中次数加1
                )
            )
            self.db.session.execute(stmt)

        return lc_documents  # 返回检索结果
