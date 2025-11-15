import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import asc, func

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.entity.cache_entity import LOCK_EXPIRE_TIME, LOCK_SEGMENT_UPDATE_ENABLED
from src.entity.dataset_entity import MAX_CREATE_TOKEN, DocumentStatus, SegmentStatus
from src.exception.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from src.lib.helper import generate_text_hash
from src.model.dataset import Document, Segment
from src.schemas.segment_schema import CreateSegmentReq, GetSegmentsWithPageReq
from src.service.base_service import BaseService
from src.service.embeddings_service import EmbeddingsService
from src.service.jieba_service import JiebaService
from src.service.keyword_table_service import KeywordTableService
from src.service.vector_database_service import VectorDatabaseService

logger = logging.getLogger(__name__)


@inject
@dataclass
class SegmentService(BaseService):
    db: SQLAlchemy
    redis_client: Redis
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService
    jieba_service: JiebaService
    embeddings_service: EmbeddingsService

    def create_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        req: CreateSegmentReq,
    ) -> Segment:
        """创建新的文档片段。

        该方法用于在指定文档中创建新的文本片段，包括：
        1. 验证输入内容的token数量是否超过限制
        2. 检查文档是否存在且有权限操作
        3. 验证文档状态是否为已完成
        4. 处理关键词（如果为空则自动提取）
        5. 创建新的文档片段并保存到数据库
        6. 将片段添加到向量数据库用于检索
        7. 更新文档的统计信息
        8. 处理关键词表

        Args:
            dataset_id (UUID): 数据集ID，用于验证权限
            document_id (UUID): 文档ID，指定要添加片段的文档
            req (CreateSegmentReq): 创建片段的请求对象，包含内容和关键词

        Returns:
            Segment: 创建成功的文档片段对象

        Raises:
            ValidateErrorException: 当输入内容超过token限制时
            NotFoundException: 当文档不存在或无权限时
            FailException: 当文档状态不正确或创建失败时

        Note:
            当前account_id是硬编码的，实际应用中应从认证信息获取

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 计算输入内容的token数量
        token_count = self.embeddings_service.calculate_token_count(req.content.data)
        # 检查token数量是否超过最大限制
        if token_count > MAX_CREATE_TOKEN:
            # 如果超过限制，构造错误信息
            error_msg = (
                f"文档片段长度超过{MAX_CREATE_TOKEN}个字符，",
                f"实际长度为{token_count}个字符",
            )
            # 抛出验证异常
            raise ValidateErrorException(error_msg)

        # 根据document_id获取文档信息
        document = self.get(Document, document_id)
        # 检查文档是否存在，以及是否有权限新增
        if (
            document is None
            or str(document.account_id) != account_id
            or document.dataset_id != dataset_id
        ):
            # 如果文档不存在或无权限，构造错误信息
            error_msg = f"文档片段所属的文档不存在或无权限新增，文档ID为{document_id}"
            # 抛出未找到异常
            raise NotFoundException(error_msg)

        # 检查文档状态是否为已完成
        if document.status != DocumentStatus.COMPLETED:
            # 如果文档未完成，构造错误信息
            error_msg = (
                f"文档片段所属的文档未完成，无法新增片段，文档状态{document.status}"
            )
            # 抛出操作失败异常
            raise FailException(error_msg)

        # 查询指定文档中最大的段落位置，如果不存在则默认为0
        position = (
            self.db.session.query(
                func.coalesce(
                    func.max(Segment.position),
                    0,
                ),  # 使用coalesce函数确保当没有记录时返回0
            )
            .filter(
                Segment.document_id == document_id,  # 筛选条件：只查找指定文档ID的记录
            )
            .scalar()  # 获取单个值，而不是整个结果集
        )

        # 检查请求中的关键字数据是否为空
        if req.keywords.data is None or len(req.keywords.data) == 0:
            # 如果关键字为空，则使用jieba服务从内容中提取10个关键字
            req.keywords.data = self.jieba_service.extract_keywords(
                req.content.data,  # 传入要分析的内容
                10,  # 提取的关键字数量
            )

        # 初始化segment变量为None
        segment = None
        try:
            # 位置计数器加1
            position += 1
            # 创建新的文档片段
            segment = self.create(
                Segment,  # 创建Segment对象
                account_id=account_id,  # 账户ID
                dataset_id=dataset_id,  # 数据集ID
                document_id=document_id,  # 文档ID
                node_id=uuid.uuid4(),  # 生成唯一节点ID
                position=position,  # 片段位置
                content=req.content.data,  # 片段内容
                character_count=len(req.content.data),  # 字符计数
                token_count=token_count,  # token计数
                keywords=req.keywords.data,  # 关键词
                hash=generate_text_hash(req.content.data),  # 内容哈希值
                enabled=True,  # 启用状态
                processing_started_at=datetime.now(UTC),  # 处理开始时间
                indexing_completed_at=datetime.now(UTC),  # 索引完成时间
                completed_at=datetime.now(UTC),  # 完成时间
                status=SegmentStatus.COMPLETED,  # 状态为已完成
            )

            # 将文档片段添加到向量数据库
            self.vector_database_service.vector_store.aadd_documents(
                [
                    LCDocument(  # 创建文档对象
                        page_content=req.content.data,  # 页面内容
                        metadata={  # 元数据
                            "account_id": str(document.account_id),
                            "dataset_id": str(document.dataset_id),
                            "document_id": str(document.id),
                            "segment_id": str(segment.id),
                            "node_id": str(segment.node_id),
                            "document_enabled": document.enabled,
                            "segment_enabled": True,
                        },
                    ),
                ],
                ids=[str(segment.node_id)],  # 使用节点ID作为文档ID
            )

            # 查询文档的总字符数和token数
            document_character_count, document_token_count = (
                self.db.session.query(
                    func.coalesce(
                        func.sum(Segment.character_count),
                        0,
                    ),  # 计算字符总数，如果没有则为0
                    func.coalesce(
                        func.sum(Segment.token_count),
                        0,
                    ),  # 计算token总数，如果没有则为0
                )
                .filter(Segment.document_id == document.id)
                .first()
            )

            # 更新文档的字符数和token数
            self.update(
                document,
                character_count=document_character_count,
                token_count=document_token_count,
            )

            # 如果文档启用，则添加关键词表
            if document.enabled is True:
                self.keyword_table_service.add_keyword_table_from_ids(
                    dataset_id,
                    [segment.id],
                )

        except Exception as e:  # 捕获异常
            # 记录错误日志
            exception_msg = f"新增文档片段失败，文档ID为{document_id}，错误信息为{e!s}"
            logger.exception(exception_msg)
            # 如果segment已创建，则更新其状态为错误
            if segment:
                self.update(
                    segment,
                    error=str(e),
                    status=SegmentStatus.ERROR,
                    enabled=False,
                    disabled_at=datetime.now(UTC),
                    stopped_at=datetime.now(UTC),
                )
            # 抛出异常
            error_msg = f"新增文档片段失败，文档ID为{document_id}"
            raise FailException(error_msg) from e

        # 返回创建的文档片段
        return segment

    def get_segment_with_page(
        self,
        dataset_id: UUID,
        document_id: UUID,
        req: GetSegmentsWithPageReq,
    ) -> tuple[list[Segment], Paginator]:
        """分页获取文档片段列表。

        该方法用于获取指定文档中的片段列表，支持分页和搜索功能：
        1. 验证文档存在性和访问权限
        2. 支持按内容关键词搜索
        3. 按位置顺序排序
        4. 返回分页结果

        Args:
            dataset_id (UUID): 数据集ID，用于验证权限
            document_id (UUID): 文档ID，指定要查询的文档
            req (GetSegmentsWithPageReq): 分页查询请求对象，
            包含页码、每页数量和搜索关键词

        Returns:
            tuple[list[Segment], Paginator]: 包含片段列表和分页信息的元组

        Raises:
            NotFoundException: 当文档不存在时
            ForbiddenException: 当无访问权限时

        Note:
            当前account_id是硬编码的，实际应用中应从认证信息获取

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 根据文档ID获取文档对象
        document = self.get(Document, document_id)
        # 检查文档是否存在
        if document is None:
            error_msg = f"文档不存在：{document_id}"
            raise NotFoundException(error_msg)
        # 验证文档所属知识库和账户权限
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            error_msg = f"无权限访问文档：{document_id}"
            raise ForbiddenException(error_msg)

        # 创建分页器对象，传入数据库连接和请求对象
        paginator = Paginator(db=self.db, req=req)

        # 初始化过滤条件列表，首先按文档ID进行过滤
        filters = [Segment.document_id == document_id]
        # 如果请求中包含搜索关键词，则添加内容模糊匹配的过滤条件
        if req.search_word.data:
            filters.append(Segment.content.ilike(f"%{req.search_word.data}%"))

        # 执行分页查询，应用所有过滤条件并按位置字段升序排序
        segments = paginator.paginate(
            self.db.session.query(Segment).filter(*filters).order_by(asc("position")),
        )

        return segments, paginator

    def get_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
    ) -> Segment:
        """获取单个文档片段信息。

        该方法用于获取指定文档片段的详细信息：
        1. 验证文档存在性和访问权限
        2. 验证片段存在性和访问权限
        3. 返回片段详细信息

        Args:
            dataset_id (UUID): 数据集ID，用于验证权限
            document_id (UUID): 文档ID，验证片段所属文档
            segment_id (UUID): 片段ID，指定要查询的片段

        Returns:
            Segment: 文档片段对象

        Raises:
            NotFoundException: 当文档或片段不存在时
            ForbiddenException: 当无访问权限时

        Note:
            当前account_id是硬编码的，实际应用中应从认证信息获取

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 根据文档ID获取文档对象
        document = self.get(Document, document_id)
        # 检查文档是否存在
        if document is None:
            error_msg = f"文档不存在：{document_id}"
            raise NotFoundException(error_msg)
        # 验证文档所属知识库和账户权限
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            error_msg = f"无权限访问文档：{document_id}"
            raise ForbiddenException(error_msg)

        segment = self.get(Segment, segment_id)
        # 检查文档片段是否存在
        if segment is None:
            error_msg = f"文档片段不存在：{segment_id}"
            raise NotFoundException(error_msg)
        # 验证段落所属文档和账户权限
        if segment.document_id != document_id or str(segment.account_id) != account_id:
            error_msg = f"无权限访问文档片段：{segment_id}"
            raise ForbiddenException(error_msg)

        return segment

    def update_segment_enabled(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
        *,
        enabled: bool,
    ) -> Segment:
        """更新文档片段的启用状态。

        该方法用于启用或禁用文档片段：
        1. 验证文档和片段的存在性及权限
        2. 验证片段状态是否为已完成
        3. 使用分布式锁防止并发更新
        4. 更新向量数据库中的状态
        5. 更新关键词表
        6. 处理异常和错误恢复

        Args:
            dataset_id (UUID): 数据集ID，用于验证权限
            document_id (UUID): 文档ID，验证片段所属文档
            segment_id (UUID): 片段ID，指定要更新的片段
            enabled (bool): 是否启用片段，True为启用，False为禁用

        Returns:
            Segment: 更新后的文档片段对象

        Raises:
            NotFoundException: 当文档或片段不存在时
            ForbiddenException: 当无访问权限时
            FailException: 当片段状态不正确或更新失败时

        Note:
            当前account_id是硬编码的，实际应用中应从认证信息获取
            使用Redis分布式锁确保并发安全性

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 根据文档ID获取文档对象
        document = self.get(Document, document_id)
        # 检查文档是否存在
        if document is None:
            error_msg = f"文档不存在：{document_id}"
            raise NotFoundException(error_msg)
        # 验证文档所属知识库和账户权限
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            error_msg = f"无权限访问文档：{document_id}"
            raise ForbiddenException(error_msg)
        # 根据文档ID和段落ID获取段落对象
        segment = self.get(Segment, segment_id)
        # 检查文档片段是否存在
        if segment is None:
            error_msg = f"文档片段不存在：{segment_id}"
            raise NotFoundException(error_msg)
        # 验证文档片段所属文档和账户权限
        if segment.document_id != document_id or str(segment.account_id) != account_id:
            error_msg = f"无权限修改文档片段：{segment_id}"
            raise ForbiddenException(error_msg)

        # 检查文档片段状态是否为已完成，如果不是则抛出异常
        if segment.status != SegmentStatus.COMPLETED:
            error_msg = f"文档片段未完成：{segment_id}，状态：{segment.status}"
            raise FailException(error_msg)

        # 检查文档片段的启用状态是否与目标状态相同，如果相同则抛出异常
        if enabled == segment.enabled:
            error_msg = f"文档片段状态未改变：{segment_id}，状态：{segment.enabled}"
            raise FailException(error_msg)

        # 生成缓存键，检查是否有其他进程正在更新文档片段状态
        cache_key = LOCK_SEGMENT_UPDATE_ENABLED.format(dataset_id=dataset_id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            error_msg = f"文档片段状态更新中：{segment_id}，状态：{segment.status}"
            raise FailException(error_msg)

        # 使用分布式锁确保更新的原子性
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            try:
                # 更新文档片段的启用状态和相关时间戳
                self.update(
                    segment,
                    enabled=enabled,
                    disabled_at=None if enabled else datetime.now(UTC),
                )

                # 如果启用文档片段且文档本身也是启用的，则添加关键词表
                if enabled is True and segment.document.enabled is True:
                    self.keyword_table_service.add_keyword_table_from_ids(
                        dataset_id,
                        [segment_id],
                    )
                else:
                    # 否则删除关键词表
                    self.keyword_table_service.delete_keyword_table_from_ids(
                        dataset_id,
                        [segment_id],
                    )

                # 更新向量数据库中的文档片段启用状态
                self.vector_database_service.collection.data.update(
                    uuid=segment.node_id,
                    properties={"segment_enabled": enabled},
                )
            except Exception as e:
                # 异常处理：记录错误日志，更新文档片段状态为错误，并禁用文档片段
                exception_msg = (
                    f"文档片段状态更新失败：{segment_id}，",
                    f"状态：{segment.status}, 错误：{e!s}",
                )
                logger.exception(exception_msg)
                self.update(
                    segment,
                    error=str(e),
                    status=SegmentStatus.ERROR,
                    enabled=False,
                    disabled_at=datetime.now(UTC),
                    stopped_at=datetime.now(UTC),
                )
                error_msg = (
                    f"文档片段状态更新失败：{segment_id}，状态：{segment.status}"
                )
                raise FailException(error_msg) from e

        return segment
