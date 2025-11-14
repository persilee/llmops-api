import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from injector import inject
from redis import Redis
from sqlalchemy import asc

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.entity.cache_entity import LOCK_EXPIRE_TIME, LOCK_SEGMENT_UPDATE_ENABLED
from src.entity.dataset_entity import SegmentStatus
from src.exception.exception import FailException, ForbiddenException, NotFoundException
from src.model.dataset import Document, Segment
from src.schemas.segment_schema import GetSegmentsWithPageReq
from src.service.base_service import BaseService
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

    def get_segment_with_page(
        self,
        dataset_id: UUID,
        document_id: UUID,
        req: GetSegmentsWithPageReq,
    ) -> tuple[list[Segment], Paginator]:
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

        paginator = Paginator(db=self.db, req=req)

        filters = [Segment.document_id == document_id]
        if req.search_word.data:
            filters.append(Segment.content.ilike(f"%{req.search_word.data}%"))

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

        if segment.status != SegmentStatus.COMPLETED:
            error_msg = f"文档片段未完成：{segment_id}，状态：{segment.status}"
            raise FailException(error_msg)

        if enabled == segment.enabled:
            error_msg = f"文档片段状态未改变：{segment_id}，状态：{segment.enabled}"
            raise FailException(error_msg)

        cache_key = LOCK_SEGMENT_UPDATE_ENABLED.format(dataset_id=dataset_id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            error_msg = f"文档片段状态更新中：{segment_id}，状态：{segment.status}"
            raise FailException(error_msg)

        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            try:
                self.update(
                    segment,
                    enabled=enabled,
                    disabled_at=None if enabled else datetime.now(UTC),
                )

                if enabled is True and segment.document.enabled is True:
                    self.keyword_table_service.add_keyword_table_from_ids(
                        dataset_id,
                        [segment_id],
                    )
                else:
                    self.keyword_table_service.delete_keyword_table_from_ids(
                        dataset_id,
                        [segment_id],
                    )

                self.vector_database_service.collection.data.update(
                    uuid=segment.node_id,
                    properties={"segment_enabled": enabled},
                )
            except Exception as e:
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
