from dataclasses import dataclass

import tiktoken
from injector import inject
from langchain.embeddings import Embeddings
from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_community.storage import RedisStore
from langchain_openai import OpenAIEmbeddings
from redis import Redis


@inject
@dataclass
class EmbeddingsService:
    """嵌入服务类，负责管理文本嵌入模型和Redis缓存

    该类提供了文本嵌入的核心功能，包括：
    - 使用HuggingFace BGE模型进行文本嵌入
    - 通过Redis缓存嵌入向量以提高性能
    - 提供token计数功能

    Attributes:
        _store (RedisStore): Redis存储实例，用于缓存嵌入向量
        _embeddings (Embeddings): 基础嵌入模型实例
        _cache_backed_embeddings (CacheBackedEmbeddings): 带有Redis缓存支持的
        嵌入模型实例

    """

    _store: RedisStore
    _embeddings: Embeddings
    _cache_backed_embeddings: CacheBackedEmbeddings

    def __init__(self, redis: Redis) -> None:
        # 初始化Redis存储，用于缓存嵌入向量
        self._store = RedisStore(client=redis)
        # OpenAI嵌入模型（已注释）
        self._embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        # 初始化HuggingFace嵌入模型，使用多语言基础模型
        # self._embeddings = HuggingFaceEmbeddings(
        #     model_name=(
        #         "Alibaba-NLP/gte-multilingual-base"
        #     ),  # 使用阿里巴巴的多语言基础模型
        #     cache_folder=str(
        #         Path.cwd() / "src" / "core" / "embeddings",
        #     ),  # 设置模型缓存目录
        #     model_kwargs={"trust_remote_code": True},  # 允许执行远程代码
        # )
        # 创建缓存支持的嵌入，将嵌入向量存储到Redis中
        self._cache_backed_embeddings = CacheBackedEmbeddings.from_bytes_store(
            self._embeddings,  # 基础嵌入模型
            self._store,  # Redis存储后端
            namespace="embeddings",  # Redis命名空间，用于区分不同类型的缓存
        )

    @classmethod
    def calculate_token_count(cls, query: str) -> int:
        """计算输入文本的token数量

        Args:
            query (str): 需要计算token数量的输入文本

        Returns:
            int: 文本对应的token数量

        Note:
            使用GPT-3.5的编码器来计算token数量，这确保了与OpenAI模型的兼容性

        """
        # 获取GPT-3.5模型的编码器
        encoding = tiktoken.encoding_for_model("gpt-3.5")
        # 对输入文本进行编码并返回token数量
        return len(encoding.encode(query))

    @property
    def store(self) -> RedisStore:
        """获取Redis存储实例

        Returns:
            RedisStore: 用于缓存嵌入向量的Redis存储实例

        """
        return self._store

    @property
    def embeddings(self) -> Embeddings:
        """获取嵌入模型实例

        Returns:
            Embeddings: 用于文本嵌入的模型实例

        """
        return self._embeddings

    @property
    def cache_backed_embeddings(self) -> CacheBackedEmbeddings:
        """获取缓存支持的嵌入模型实例

        Returns:
            CacheBackedEmbeddings: 带有Redis缓存支持的嵌入模型实例

        """
        return self._cache_backed_embeddings
