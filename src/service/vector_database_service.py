from dataclasses import dataclass

from flask_weaviate import FlaskWeaviate
from injector import inject
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_weaviate import WeaviateVectorStore
from weaviate.collections import Collection

from src.service.embeddings_service import EmbeddingsService

COLLECTION_NAME = "Dataset"


@inject
@dataclass
class VectorDatabaseService:
    """向量数据库服务类，负责管理与Weaviate向量数据库的连接和操作。

    该类提供了向量数据库的初始化、文档检索和文档合并等功能。它使用Weaviate作为向量数据库后端，
    通过EmbeddingsService生成文本向量，并提供了便捷的检索器接口用于相似性搜索。

    Attributes:
        client (WeaviateClient): Weaviate数据库客户端实例
        vector_store (WeaviateVectorStore): Weaviate向量存储实例
        embeddings_service (EmbeddingsService): 嵌入服务实例，用于生成文本向量

    Dependencies:
        - Weaviate: 作为向量数据库后端
        - EmbeddingsService: 用于生成文本向量

    Usage:
        service = VectorDatabaseService(embeddings_service)
        retriever = service.get_retriever()
        documents = retriever.get_relevant_documents(query)
        combined_text = VectorDatabaseService.combine_documents(documents)

    """

    weaviate: FlaskWeaviate
    embeddings_service: EmbeddingsService

    @property
    def vector_store(self) -> WeaviateVectorStore:
        return WeaviateVectorStore(
            client=self.weaviate.client,
            index_name=COLLECTION_NAME,
            text_key="text",
            embedding=self.embeddings_service.cache_backed_embeddings,
        )

    def get_retriever(self) -> VectorStoreRetriever:
        """获取向量存储的检索器实例

        Returns:
            VectorStoreRetriever: 向量存储检索器实例，用于执行相似性搜索和文档检索

        """
        return self.vector_store.as_retriever()

    @property
    def collection(self) -> Collection:
        return self.weaviate.client.collections.get(COLLECTION_NAME)
