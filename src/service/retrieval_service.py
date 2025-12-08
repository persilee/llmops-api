from dataclasses import dataclass
from uuid import UUID

from injector import inject
from langchain.tools import BaseTool, tool
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document as LCDocument
from pydantic import BaseModel, Field
from sqlalchemy import update

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from src.entity.dataset_entity import RetrievalSource, RetrievalStrategy
from src.exception.exception import NotFoundException
from src.lib.helper import combine_documents
from src.model.account import Account
from src.model.dataset import Dataset, DatasetQuery, Segment
from src.service.base_service import BaseService
from src.service.jieba_service import JiebaService
from src.service.vector_database_service import VectorDatabaseService


@dataclass
class RetrievalConfig:
    dataset_ids: list[UUID]
    account: Account
    retrieval_strategy: str = RetrievalStrategy.SEMANTIC
    k: int = 4
    score: float = 0
    retrieval_source: str = RetrievalSource.HIT_TESTING


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

    def create_langchain_tool_from_search(self, config: RetrievalConfig) -> BaseTool:
        """创建一个用于知识库搜索的LangChain工具。

        该方法创建一个可被LangChain使用的工具，用于在指定的知识库中搜索相关内容。
        工具支持语义检索、全文检索和混合检索等多种检索策略。

        Args:
            config (RetrievalConfig): 检索配置对象，包含以下属性：
                - dataset_ids: 要搜索的知识库ID列表
                - account: 执行搜索的账户信息
                - retrieval_strategy: 检索策略（语义/全文/混合）
                - k: 返回结果数量
                - score: 相似度阈值
                - retrieval_source: 检索来源

        Returns:
            BaseTool: 返回一个配置好的LangChain工具实例，该工具可以：
                - 接收查询字符串作为输入
                - 在指定的知识库中执行搜索
                - 返回格式化的搜索结果
                - 处理无结果的情况

        """

        # 定义输入数据模型，用于验证和描述工具的输入参数
        class DatasetRetrievalInput(BaseModel):
            query: str = Field(description="知识库搜索的查询语句，例如：'python'")

        # 使用@tool装饰器创建LangChain工具，指定工具名称和输入模式
        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """工具描述：如果需要搜索扩展的知识库内容，当你觉得用户的提问超过你的知识范围时，可以尝试调用该工具

            输入：搜索query语句
            输出：检索内容字符串
            """
            # 调用search_in_datasets方法执行知识库搜索
            documents = self.search_in_datasets(
                dataset_ids=config.dataset_ids,  # 指定要搜索的知识库ID列表
                query=query,  # 搜索查询语句
                account=config.account,  # 执行搜索的账户信息
                retrieval_strategy=config.retrieval_strategy,  # 检索策略
                k=config.k,  # 返回结果数量
                score=config.score,  # 相似度阈值
                retrieval_source=config.retrieval_source,  # 检索来源
            )

            # 检查是否找到相关文档
            if len(documents) == 0:
                return "没有找到相关内容，请重新输入问题"

            # 使用combine_documents函数将检索到的文档合并为一个字符串
            return combine_documents(documents)

        # 返回创建的工具
        return dataset_retrieval
