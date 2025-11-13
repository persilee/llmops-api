import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from flask import Flask, current_app
from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.file_extractor.file_extractor import FileExtractor
from src.entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED
from src.entity.dataset_entity import DocumentStatus, SegmentStatus
from src.exception.exception import NotFoundException
from src.lib.helper import generate_text_hash
from src.model.dataset import Document, Segment
from src.service.base_service import BaseService
from src.service.embeddings_service import EmbeddingsService
from src.service.jieba_service import JiebaService
from src.service.keyword_table_service import KeywordTableService
from src.service.process_rule_service import ProcessRuleService
from src.service.vector_database_service import VectorDatabaseService

logger = logging.getLogger(__name__)


@inject
@dataclass
class IndexingService(BaseService):
    """文档索引处理服务类。

    该服务负责处理文档的完整索引流程，包括：
    1. 文档解析：将上传的文件转换为可处理的文本格式
    2. 文档分割：根据处理规则将文档分割成合适的段落
    3. 文档索引：对段落进行关键词提取和索引处理
    4. 向量存储：将处理后的段落存储到向量数据库中
    5. 状态更新：更新文档和段落的索引状态

    依赖组件：
    - db: 数据库访问组件
    - file_extractor: 文件提取器，用于解析各种格式的文件
    - process_rule_service: 处理规则服务，用于文档分割和清理
    - embeddings_service: 嵌入向量服务，用于计算token数量
    - jieba_service: 中文分词服务，用于关键词提取
    - keyword_table_service: 关键词表服务，用于维护关键词映射
    - vector_database_service: 向量数据库服务，用于文档向量存储

    主要方法：
    - build_documents: 构建文档索引的主入口方法
    - update_document_enabled: 更新文档的启用状态
    - _parsing: 解析文档内容
    - _splitting: 分割文档段落
    - _indexing: 处理文档索引
    - _completed: 完成文档处理
    - _clean_extra_text: 清理文本内容

    Attributes:
        db (SQLAlchemy): 数据库访问实例
        file_extractor (FileExtractor): 文件提取器实例
        process_rule_service (ProcessRuleService): 处理规则服务实例
        embeddings_service (EmbeddingsService): 嵌入向量服务实例
        jieba_service (JiebaService): 中文分词服务实例
        keyword_table_service (KeywordTableService): 关键词表服务实例
        vector_database_service (VectorDatabaseService): 向量数据库服务实例
        redis_client (Redis): Redis实例

    """

    db: SQLAlchemy
    file_extractor: FileExtractor
    process_rule_service: ProcessRuleService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService
    redis_client: Redis

    def update_document_enabled(self, document_id: UUID) -> None:
        """更新文档的启用状态。

        该方法用于更新指定文档的启用状态，并同步更新向量数据库中所有相关段落的启用状态。
        使用缓存锁防止并发更新，并在出现异常时进行状态回滚。

        Args:
            document_id (UUID): 要更新状态的文档ID

        Raises:
            NotFoundException: 当指定的文档不存在时抛出
            Exception: 当更新向量数据库失败时抛出

        Returns:
            None

        """
        # 生成文档更新锁的缓存键，用于防止并发更新
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)
        # 从数据库中获取指定ID的文档
        document = self.get(Document, document_id)
        # 检查文档是否存在
        if document is None:
            error_msg = f"文档ID为{document_id}的文档不存在"
            # 记录错误日志
            logger.exception(error_msg)
            # 抛出文档不存在的异常
            raise NotFoundException(error_msg)

        # 查询文档下所有段落的node_id
        node_ids = [
            node_id
            for (node_id,) in self.db.session.query(Segment)
            .with_entities(Segment.node_id)  # 只查询node_id字段
            .filter(
                Segment.document_id == document_id,  # 筛选指定文档的段落
            )
        ]

        try:
            # 获取向量数据库的集合对象
            collection = self.vector_database_service.collection
            # 遍历所有段落，更新其在向量数据库中的启用状态
            for node_id in node_ids:
                collection.data.update(
                    uuid=node_id,  # 段落的唯一标识
                    properties={
                        "document_enabled": document.enabled,  # 更新文档的启用状态
                    },
                )
        except Exception as e:
            # 如果更新失败，记录错误信息
            error_msg = f"更新文档ID为{document_id}的文档索引失败, error: {e!s}"
            logger.exception(error_msg)
            # 获取原始的启用状态（当前状态的相反值）
            origin_enabled = not document.enabled
            # 回滚文档的启用状态
            self.update(
                document,
                enabled=origin_enabled,  # 恢复原始状态
                disabled_at=None
                if origin_enabled
                else datetime.now(UTC),  # 更新禁用时间
            )
        finally:
            # 无论成功还是失败，最后都要删除更新锁缓存
            self.redis_client.delete(cache_key)

    def build_documents(self, document_ids: list[UUID]) -> None:
        """构建文档索引的主方法

        Args:
            document_ids: 需要构建索引的文档ID列表

        """
        # 从数据库中查询指定ID的文档
        documents = (
            self.db.session.query(Document)
            .filter(
                Document.id.in_(document_ids),
            )
            .all()
        )

        # 遍历每个文档进行处理
        for document in documents:
            try:
                # 更新文档状态为"解析中"，并记录开始处理时间
                self.update(
                    document,
                    status=DocumentStatus.PARSING,
                    processing_started_at=datetime.now(UTC),
                )

                # 第一步：解析文档内容，转换为LangChain文档格式
                lc_documents = self._parsing(document)

                # 第二步：将文档分割成多个段落
                lc_segments = self._splitting(document, lc_documents)

                # 第三步：对文档段落进行索引处理
                self._indexing(document, lc_segments)

                # 第四步：处理文档完成后的操作，包括设置段落状态、分批处理和更新文档状态
                self._completed(document, lc_segments)

            except (ValueError, RuntimeError) as e:
                # 捕获处理过程中的异常
                error_msg = f"文档构建失败，id: {document.id}, 错误信息: {e!s}"
                # 记录详细的错误日志
                logger.exception(error_msg)
                # 更新文档状态为错误，并记录错误信息和停止时间
                self.update(
                    document,
                    status=DocumentStatus.ERROR,
                    error=str(e),
                    stopped_at=datetime.now(UTC),
                )

    def _completed(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """完成文档处理的最后阶段。

        该方法负责完成文档处理的最后步骤，包括：
        1. 设置所有文档段落的启用状态
        2. 分批将段落添加到向量数据库
        3. 更新数据库中段落的状态为已完成
        4. 更新整个文档的状态为已完成

        Args:
            document (Document): 要完成的文档对象
            lc_segments (list[LCDocument]): 文档的段落列表，
            每个段落是LangChain的Document对象

        Returns:
            None

        """
        # 遍历所有文档段落，设置启用状态
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True  # 启用文档
            lc_segment.metadata["segment_enabled"] = True  # 启用段落

        def thread_func(
            app: Flask,
            chunks: list[LCDocument],
            ids: list[UUID],
        ) -> None:
            # 创建Flask应用上下文，确保可以访问应用配置和数据库连接
            with app.app_context():
                try:
                    # 将当前批次的文档段落添加到向量数据库中
                    self.vector_database_service.vector_store.add_documents(
                        chunks,
                        ids=ids,
                    )

                    # 使用自动提交事务更新数据库
                    with self.db.auto_commit():
                        # 查询并更新指定ID的段落状态
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids),  # 筛选指定ID的段落
                        ).update(
                            {
                                # 设置段落状态为已完成
                                "status": SegmentStatus.COMPLETED,
                                # 记录完成时间（使用UTC时间）
                                "completed_at": datetime.now(UTC),
                                # 启用该段落，使其可用于搜索
                                "enabled": True,
                            },
                        )
                except Exception as e:
                    # 构造错误信息，包含具体的异常内容
                    error_msg = f"构建文档片段异常：{e!s}"
                    # 记录异常日志，包含完整的错误堆栈信息
                    logger.exception(error_msg)
                    # 在发生异常时，使用自动提交事务更新数据库
                    with self.db.auto_commit():
                        # 查询并更新出错段落的状态
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids),
                        ).update(
                            {
                                # 设置段落状态为错误
                                "status": SegmentStatus.ERROR,
                                # 记录错误发生时间（使用UTC时间）
                                "completed_at": datetime.now(UTC),
                                # 禁用该段落，使其不可用于搜索
                                "enabled": False,
                            },
                        )

        # 创建线程池，最大工作线程数为5
        with ThreadPoolExecutor(max_workers=5) as executor:
            # 用于存储所有异步任务的Future对象
            futures = []
            # 分批处理文档段落，每批10个
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i : i + 10]  # 获取当前批次的段落
                ids = [chunk.metadata["node_id"] for chunk in chunks]  # 提取段落ID列表

                app = current_app._get_current_object()  # noqa: SLF001
                if hasattr(app, "app"):  # 如果是AppContext对象，获取其app属性
                    app = app.app

                # 提交异步任务到线程池
                futures.append(
                    executor.submit(
                        thread_func,
                        app,
                        chunks,
                        ids,
                    ),
                )
            # 等待所有异步任务完成
            for future in futures:
                future.result()  # 获取任务结果，如果任务抛出异常，这里会重新抛出

        # 更新整个文档的状态
        self.update(
            document,
            status=DocumentStatus.COMPLETED,
            completed_at=datetime.now(UTC),
            enabled=True,
        )

    def _indexing(
        self,
        document: Document,
        lc_segments: list[LCDocument],
    ) -> None:
        """处理文档索引的核心方法。

        该方法负责完成文档的索引处理，包括：
        1. 对每个段落提取关键词
        2. 更新段落的索引状态和完成时间
        3. 维护关键词表，建立关键词与段落的映射关系
        4. 更新文档的索引完成时间

        Args:
            document (Document): 需要索引的文档对象
            lc_segments (list[LCDocument]): 文档分割后的段落列表，
            每个段落包含内容和元数据

        Returns:
            None: 该方法不返回任何值，直接更新数据库中的记录

        """
        # 遍历所有文档段落
        for lc_segment in lc_segments:
            # 使用jieba服务提取段落内容的前10个关键词
            keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)

            # 更新数据库中的段落记录
            self.db.session.query(Segment).filter(
                Segment.id == lc_segment.metadata["segment_id"],
            ).update(
                {
                    # 设置提取的关键词
                    "keywords": keywords,
                    # 更新段落状态为已索引
                    "status": SegmentStatus.INDEXING,
                    # 记录索引完成时间
                    "indexing_completed_at": datetime.now(UTC),
                },
            )

            # 获取数据集对应的关键词表记录
            keyword_table_record = (
                self.keyword_table_service.get_keyword_table_form_dataset_id(
                    document.dataset_id,
                )
            )
            # 将关键词表转换为集合形式，便于去重和快速查找
            keyword_table = {
                field: set(value)
                for field, value in keyword_table_record.keyword_table.items()
            }

            # 更新关键词表，记录每个关键词对应的段落ID
            for keyword in keywords:
                # 如果关键词不存在，创建新的集合
                if keyword not in keyword_table:
                    keyword_table[keyword] = set()
                # 将当前段落ID添加到关键词对应的集合中
                keyword_table[keyword].add(lc_segment.metadata["segment_id"])

            # 更新关键词表记录，将集合转换回列表形式
            self.update(
                keyword_table_record,
                keyword_table={
                    field: list(value) for field, value in keyword_table.items()
                },
            )

        # 更新文档的索引完成时间
        self.update(
            document,
            indexing_completed_at=datetime.now(UTC),
        )

    def _splitting(
        self,
        document: Document,
        lc_documents: list[LCDocument],
    ) -> list[LCDocument]:
        """将文档分割成多个段落，并创建对应的数据库记录

        Args:
            document: 要处理的文档对象
            lc_documents: LangChain文档列表，包含要分割的文本内容

        Returns:
            list[LCDocument]: 分割后的LangChain文档列表，每个文档包含元数据信息

        """
        # 获取文档的处理规则
        process_rule = document.process_rule
        # 根据处理规则获取文本分割器
        text_splitter = self.process_rule_service.get_text_splitter_by_process_rule(
            process_rule,
            self.embeddings_service.calculate_token_count,
        )

        # 清理每个文档的文本内容
        for lc_document in lc_documents:
            lc_document.page_content = (
                self.process_rule_service.clean_text_by_process_rule(
                    lc_document.page_content,
                    process_rule,
                )
            )

        # 使用分割器将文档分割成多个段落
        lc_segments = text_splitter.split_documents(lc_documents)
        # 获取当前文档的最大段落位置
        position = (
            self.db.session.query(func.coalesce(func.max(Segment.position), 0))
            .filter(
                Segment.document_id == document.id,
            )
            .scalar()
        )

        segments = []
        # 处理每个分割后的段落
        for lc_segment in lc_segments:
            position += 1
            content = lc_segment.page_content
            # 创建新的段落记录
            segment = self.create(
                Segment,
                account_id=document.account_id,
                dataset_id=document.dataset_id,
                document_id=document.id,
                node_id=uuid.uuid4(),
                position=position,
                content=content,
                character_count=len(content),
                token_count=self.embeddings_service.calculate_token_count(content),
                hash=generate_text_hash(content),
                status=SegmentStatus.WAITING,
            )
            # 设置段落的元数据信息
            lc_segment.metadata = {
                "account_id": str(document.account_id),
                "dataset_id": str(document.dataset_id),
                "document_id": str(document.id),
                "segment_id": str(segment.id),
                "node_id": str(segment.node_id),
                "document_enabled": False,
                "segment_enabled": False,
            }
            segments.append(segment)

        # 更新文档状态和统计信息
        self.update(
            document,
            token_count=sum([segment.token_count for segment in segments]),
            status=DocumentStatus.INDEXING,
            splitting_completed_at=datetime.now(UTC),
        )

        return lc_segments

    def _parsing(self, document: Document) -> list[LCDocument]:
        """解析文档内容，将上传的文件转换为LangChain文档格式。

        Args:
            document (Document): 待解析的文档对象，包含上传文件信息

        Returns:
            list[LCDocument]: 解析后的LangChain文档列表，每个文档都经过文本清理处理

        Process:
            1. 从文档对象获取上传文件
            2. 使用file_extractor加载文件内容，启用非结构化模式
            3. 对每个文档进行文本清理
            4. 更新文档状态为SPLITTING，记录字符数和处理开始时间

        """
        # 获取文档的上传文件对象
        upload_file = document.upload_file
        # 使用文件提取器加载文件内容，is_unstructured=True表示使用非结构化方式解析
        lc_documents = self.file_extractor.load(upload_file, is_unstructured=True)

        # 遍历每个解析后的文档
        for lc_document in lc_documents:
            # 清理文档中的多余文本，如特殊字符、空白等
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        # 更新文档信息：
        # - character_count: 计算所有文档内容的总字符数
        # - status: 将文档状态更新为SPLITTING（分割中）
        # - parsing_completed_at: 记录解析完成的时间
        self.update(
            document,
            character_count=sum(
                [len(lc_document.page_content) for lc_document in lc_documents],
            ),
            status=DocumentStatus.SPLITTING,
            parsing_completed_at=datetime.now(UTC),
        )

        # 返回处理后的文档列表
        return lc_documents

    @classmethod
    def _clean_extra_text(cls, text: str) -> str:
        """清理文本中的特殊字符和无效字符

        Args:
            text (str): 需要清理的原始文本

        Returns:
            str: 清理后的文本

        清理规则：
        1. 移除 Unicode 无效字符\ufffe
        2. 移除控制字符（ASCII 0-31，除了0x09, 0x0A, 0x0D）和DEL字符(0x7F)
        3. 将"|>"替换为">"
        4. 将"<|"替换为"<"

        """
        return re.sub(
            r"<\|",
            "<",
            re.sub(
                r"\|>",
                ">",
                re.sub(
                    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]",
                    "",
                    re.sub("\ufffe", "", text),
                ),
            ),
        )
