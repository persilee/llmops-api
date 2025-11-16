from uuid import UUID

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever
from langchain_weaviate import WeaviateVectorStore
from pydantic import Field
from weaviate.classes.query import Filter


class SemanticRetriever(BaseRetriever):
    dataset_ids: list[UUID]
    vector_store: WeaviateVectorStore
    search_kwargs: dict = Field(default_factory=dict)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[LCDocument]:
        """执行语义搜索并返回相关文档。

        Args:
            query (str): 查询字符串，用于搜索相关文档。
            run_manager (CallbackManagerForRetrieverRun): 回调管理器，
            用于管理检索过程中的回调。

        Returns:
            list[LCDocument]: 包含相关文档的列表，每个文档的元数据中都包含相关性分数。
                如果没有找到相关文档，则返回空列表。

        该方法会执行以下操作：
        1. 从search_kwargs中获取要返回的文档数量k，默认为4
        2. 使用向量存储进行相似性搜索，应用以下过滤条件：
           - 文档ID必须在指定的dataset_ids列表中
           - 文档必须启用
           - 文档片段必须启用
        3. 将相关性分数添加到每个文档的元数据中
        4. 返回带有分数的文档列表

        """
        # 获取要返回的文档数量，默认为4
        k = self.search_kwargs.pop("k", 4)

        # 使用向量存储进行相似性搜索，并获取相关性分数
        search_result = self.vector_store.similarity_search_with_relevance_scores(
            query=query,  # 查询字符串
            k=k,  # 返回的最大文档数
            **{
                # 设置过滤条件，必须同时满足以下所有条件：
                "filters": Filter.all_of(
                    [
                        # 1. 文档ID必须在指定的dataset_ids列表中
                        Filter.by_property("dataset_id").contains_any(
                            [str(dataset_id) for dataset_id in self.dataset_ids],
                        ),
                        # 2. 文档必须启用
                        Filter.by_property("document_enabled").equal(val=True),
                        # 3. 文档片段必须启用
                        Filter.by_property("segment_enabled").equal(val=True),
                    ],
                ),
                # 添加其他搜索参数
                **self.search_kwargs,
            },
        )

        # 如果没有搜索结果，返回空列表
        if search_result is None or len(search_result) == 0:
            return []

        # 将搜索结果解包为文档列表和分数列表
        lc_documents, scores = zip(
            *search_result,
            strict=False,
        )

        # 为每个文档添加相关性分数到元数据中
        for lc_document, score in zip(lc_documents, scores, strict=False):
            lc_document.metadata["score"] = score

        # 返回带有分数的文档列表
        return list(lc_documents)
