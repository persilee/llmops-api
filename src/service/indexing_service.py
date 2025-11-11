import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from injector import inject
from langchain_core.documents import Document as LCDocument
from sqlalchemy import func

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.file_extractor.file_extractor import FileExtractor
from src.entity.dataset_entity import DocumentStatus, SegmentStatus
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

    """

    db: SQLAlchemy
    file_extractor: FileExtractor
    process_rule_service: ProcessRuleService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService

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

        # 分批处理文档段落，每批10个
        for i in range(0, len(lc_segments), 10):
            chunks = lc_segments[i : i + 10]  # 获取当前批次的段落
            ids = [chunk.metadata["node_id"] for chunk in chunks]  # 提取段落ID

            # 将当前批次的段落添加到向量数据库
            self.vector_database_service.vector_store.aadd_documents(chunks, ids=ids)

            # 更新数据库中对应段落的状态
            self.db.session.query(Segment).filter(
                Segment.node_id.in_(ids),
            ).update(
                {
                    "status": SegmentStatus.COMPLETED,  # 设置为已完成状态
                    "completed_at": datetime.now(UTC),  # 记录完成时间
                    "enabled": True,  # 启用段落
                },
            )

        # 更新整个文档的状态
        self.update(
            document,
            status=DocumentStatus.COMPLETED,  # 设置文档为已完成状态
            completed_at=datetime.now(UTC),  # 记录文档完成时间
            enabled=True,  # 启用文档
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
        upload_file = document.upload_file
        lc_documents = self.file_extractor.load(upload_file, is_unstructured=True)

        for lc_document in lc_documents:
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        self.update(
            document,
            character_count=sum(
                [len(lc_document.page_content) for lc_document in lc_documents],
            ),
            status=DocumentStatus.SPLITTING,
            parsing_completed_at=datetime.now(UTC),
        )

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
