import os

import weaviate
from injector import inject
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_weaviate import WeaviateVectorStore
from weaviate import WeaviateClient
from weaviate.collections import Collection

from src.service.embeddings_service import EmbeddingsService

COLLECTION_NAME = "Dataset"


@inject
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

    client: WeaviateClient
    vector_store: WeaviateVectorStore
    embeddings_service: EmbeddingsService

    def __init__(self, embeddings_service: EmbeddingsService) -> None:
        """初始化向量数据库服务

        Args:
            embeddings_service (EmbeddingsService): 嵌入服务实例，用于生成文本向量

        """
        self.embeddings_service = embeddings_service
        # 连接到本地Weaviate实例
        self.client = weaviate.connect_to_local(
            host=os.getenv("WEAVIATE_HOST"),  # 从环境变量获取Weaviate主机地址
            port=int(os.getenv("WEAVIATE_PORT")),  # 从环境变量获取Weaviate端口
        )

        # 以下是连接到Weaviate云服务的配置（当前被注释）
        # self.client = weaviate.connect_to_weaviate_cloud(
        #     cluster_url=os.getenv("WEAVIATE_CLUSTER_URL"),
        #     auth_credentials=Auth.api_key(os.getenv("WEAVIATE_API_KEY")),
        # )

        # 初始化Weaviate向量存储
        self.vector_store = WeaviateVectorStore(
            client=self.client,  # Weaviate客户端实例
            index_name=COLLECTION_NAME,  # 索引名称
            text_key="text",  # 文本内容的键名
            embedding=self.embeddings_service.embeddings,  # 嵌入模型
        )

    def get_retriever(self) -> VectorStoreRetriever:
        """获取向量存储的检索器实例

        Returns:
            VectorStoreRetriever: 向量存储检索器实例，用于执行相似性搜索和文档检索

        """
        return self.vector_store.as_retriever()

    @property
    def collection(self) -> Collection:
        return self.client.collections.get(COLLECTION_NAME)
