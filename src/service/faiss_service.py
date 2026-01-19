import logging
from pathlib import Path

from injector import inject
from langchain_community.vectorstores import FAISS
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from src.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from src.lib.helper import combine_documents

from .embeddings_service import EmbeddingsService

logger = logging.getLogger(__name__)


@inject
class FaissService:
    """Faiss向量数据库服务"""

    faiss: FAISS
    embeddings_service: EmbeddingsService

    def __init__(self, embeddings_service: EmbeddingsService) -> None:
        """构造函数，完成Faiss向量数据库的初始化"""
        # 1.赋值embeddings_service
        self.embeddings_service = embeddings_service

        # 2.获取src路径并计算本地向量数据库的实际路径
        faiss_vector_store_path = Path(__file__).parent.parent / "core" / "vector_store"
        index_name = "index"

        # 3.初始化faiss向量数据库
        try:
            if faiss_vector_store_path.exists():
                self.faiss = FAISS.load_local(
                    folder_path=str(faiss_vector_store_path),
                    embeddings=self.embeddings_service.embeddings,
                    index_name=index_name,
                    allow_dangerous_deserialization=True,
                )
                # 验证索引维度
                if hasattr(self.faiss.index, "d"):
                    print(f"FAISS索引维度: {self.faiss.index.d}")
            else:
                # 创建目录
                faiss_vector_store_path.mkdir(parents=True, exist_ok=True)
                # 创建空索引
                self.faiss = FAISS.from_texts(
                    texts=[""],  # 使用空文本创建初始索引
                    embedding=self.embeddings_service.embeddings,
                )
                # 保存索引
                self.faiss.save_local(
                    folder_path=str(faiss_vector_store_path),
                    index_name=index_name,
                )
                info_msg = f"创建新的FAISS索引: {faiss_vector_store_path / index_name}"
                logger.info(info_msg)
        except Exception as e:
            error_msg = f"加载FAISS索引失败: {e}"
            logger.exception(error_msg)
            raise

    def convert_faiss_to_tool(self) -> BaseTool:
        """将Faiss向量数据库检索器转换成LangChain工具"""
        # 1.将Faiss向量数据库转换成检索器
        retrieval = self.faiss.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 20},
        )

        # 2.构建检索链，并将检索的结果合并成字符串
        search_chain = retrieval | combine_documents

        class DatasetRetrievalInput(BaseModel):
            """知识库检索工具输入结构"""

            query: str = Field(description="知识库检索query语句，类型为字符串")

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """如果需要检索扩展的知识库内容，当你觉得用户的提问超过你的知识范围时，可以尝试调用该工具，输入为搜索query语句，返回数据为检索内容字符串"""
            return search_chain.invoke(query)

        return dataset_retrieval
