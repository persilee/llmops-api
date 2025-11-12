import logging
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import asc, desc, func

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from src.entity.dataset_entity import ProcessType, SegmentStatus
from src.entity.upload_file_entity import ALLOWED_DOCUMENT_EXTENSION
from src.exception.exception import FailException, ForbiddenException, NotFoundException
from src.lib.helper import datetime_to_timestamp
from src.model.dataset import Dataset, Document, ProcessRule, Segment
from src.model.upload_file import UploadFile
from src.schemas.document_schema import GetDocumentsWithPageReq
from src.service.base_service import BaseService
from src.task.document_task import build_documents

logger = logging.getLogger(__name__)


@inject
@dataclass
class DocumentService(BaseService):
    db: SQLAlchemy

    def get_documents_with_page(
        self,
        dataset_id: UUID,
        req: GetDocumentsWithPageReq,
    ) -> tuple[list[Document], Paginator]:
        """获取知识库中的文档列表（分页）

        Args:
            dataset_id: 知识库ID
            req: 分页请求参数，包含页码、每页数量、搜索关键词等

        Returns:
            tuple[list[Document], Paginator]: 返回文档列表和分页器对象

        Raises:
            NotFoundException: 当知识库不存在或无权限访问时抛出

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"
        # 获取知识库信息并验证权限
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            error_msg = "知识库不存在或无权限访问"
            raise NotFoundException(error_msg)

        # 初始化分页器
        paginator = Paginator(db=self.db, req=req)

        # 构建查询过滤器
        filters = [
            Document.account_id == account_id,  # 账户ID过滤
            Document.dataset_id == dataset_id,  # 知识库ID过滤
        ]
        # 如果有搜索关键词，添加名称模糊匹配条件
        if req.search_word.data:
            filters.append(Document.name.ilike(f"%{req.search_word.data}%"))

        # 执行分页查询，按创建时间倒序排列
        documents = paginator.paginate(
            self.db.session.query(Document)
            .filter(*filters)
            .order_by(desc("created_at")),
        )

        return documents, paginator

    def update_document_name(
        self,
        dataset_id: UUID,  # 知识库ID
        document_id: UUID,  # 文档ID
        **kwargs: dict,  # 更新的文档属性，如name等
    ) -> Document:  # 返回更新后的文档对象
        """更新文档名称和属性。

        Args:
            dataset_id (UUID): 知识库ID，用于验证文档所属知识库
            document_id (UUID): 要更新的文档ID
            **kwargs (dict): 要更新的文档属性字典，如name等

        Returns:
            Document: 更新后的文档对象

        Raises:
            NotFoundException: 当文档不存在时抛出
            ForbiddenException: 当用户无权限修改文档时抛出

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"  # 临时硬编码的账户ID

        # 根据文档ID获取文档对象
        document = self.get(Document, document_id)
        # 检查文档是否存在
        if document is None:
            error_msg = f"文档不存在：{document_id}"
            raise NotFoundException(error_msg)  # 抛出文档不存在的异常
        # 验证文档所属知识库和账户权限
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            error_msg = f"无权限修改文档：{document_id}"
            raise ForbiddenException(error_msg)  # 抛出无权限异常

        # 更新文档属性并返回更新后的文档对象
        return self.update(document, **kwargs)

    def get_document(self, dataset_id: UUID, document_id: UUID) -> Document:
        """获取指定文档信息

        Args:
            dataset_id: 知识库ID
            document_id: 文档ID

        Returns:
            Document: 文档对象

        Raises:
            NotFoundException: 当文档不存在时
            ForbiddenException: 当无权限访问文档时

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

        return document

    def create_documents(
        self,
        dataset_id: UUID,
        upload_file_ids: list[UUID],
        process_type: str = ProcessType.AUTOMATIC,
        rule: dict | None = None,
    ) -> tuple[list[Document], str]:
        """创建文档

        Args:
            dataset_id: 知识库ID
            upload_file_ids: 上传文件ID列表
            process_type: 处理类型，默认为自动处理
            rule: 处理规则，可选参数

        Returns:
            tuple[list[Document], str]: 返回创建的文档列表和批次号

        Raises:
            ForbiddenException: 当用户无权限或知识库不存在时抛出
            FailException: 当上传文件格式不支持时抛出

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 获取知识库并验证权限
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            error_msg = "无权限或知识库不存在"
            raise ForbiddenException(error_msg)

        # 查询并过滤上传文件
        upload_files = (
            self.db.session.query(UploadFile)
            .filter(
                UploadFile.account_id == account_id,
                UploadFile.id.in_(upload_file_ids),
            )
            .all()
        )
        # 只保留允许的文档格式
        upload_files = [
            file
            for file in upload_files
            if file.extension.lower() in ALLOWED_DOCUMENT_EXTENSION
        ]
        # 检查是否有有效的上传文件
        if len(upload_files) == 0:
            logger.warning(
                "上传文件格式不支持, account_id: %s, dataset_id: %s, "
                "upload_file_ids: %s",
                account_id,
                dataset_id,
                upload_file_ids,
            )

            error_msg = "上传文件格式不支持"
            raise FailException(error_msg)

        # 生成唯一的批次号：时间戳+随机数
        batch = time.strftime("%Y%m%d%H%M%S") + str(
            secrets.randbits(20),
        )
        # 创建处理规则
        process_rule = self.create(
            ProcessRule,
            account_id=account_id,
            dataset_id=dataset_id,
            mode=process_type,
            rule=rule,
        )
        # 获取最新的文档位置
        position = self.get_latest_document_position(dataset_id)

        # 创建文档列表
        documents = []
        for upload_file in upload_files:
            position += 1
            # 创建文档记录
            document = self.create(
                Document,
                account_id=account_id,
                dataset_id=dataset_id,
                upload_file_id=upload_file.id,
                process_rule_id=process_rule.id,
                batch=batch,
                name=upload_file.name,
                position=position,
            )
            documents.append(document)

        # 异步处理文档：将文档ID列表传递给Celery任务队列，进行后台文档处理
        build_documents.delay([document.id for document in documents])

        return documents, batch

    def get_latest_document_position(self, dataset_id: UUID) -> int:
        """获取数据集中最新文档的位置编号

        Args:
            dataset_id (UUID): 数据集的唯一标识符

        Returns:
            int: 返回最新文档的position值。如果数据集中没有文档，则返回0

        """
        document = (
            self.db.session.query(Document)
            .filter(
                Document.dataset_id == dataset_id,
            )
            .order_by(desc("position"))
            .first()
        )

        return document.position if document else 0

    def get_documents_status(self, dataset_id: UUID, batch: str) -> list[dict]:
        """获取指定批次文档的状态信息

        Args:
            dataset_id (UUID): 知识库ID
            batch (str): 文档批次号

        Returns:
            list[dict]: 文档状态信息列表，每个字典包含以下字段：
                - id: 文档ID
                - name: 文档名称
                - size: 文件大小
                - extension: 文件扩展名
                - mime_type: MIME类型
                - position: 文档位置
                - segment_count: 分段总数
                - completed_segment_count: 已完成分段数
                - error: 错误信息
                - status: 文档状态
                - processing_started_at: 处理开始时间戳
                - parsing_completed_at: 解析完成时间戳
                - splicing_completed_at: 拼接完成时间戳
                - indexing_completed_at: 索引完成时间戳
                - completed_at: 完成时间戳
                - stopped_at: 停止时间戳
                - created_at: 创建时间戳

        Raises:
            ForbiddenException: 当用户无权限访问知识库时
            NotFoundException: 当未找到指定批次的文档时

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 获取知识库并验证权限
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            error_msg = "无权限或知识库不存在"
            raise ForbiddenException(error_msg)

        # 查询指定批次的所有文档，按位置升序排列
        documents = (
            self.db.session.query(Document)
            .filter(
                Document.dataset_id == dataset_id,
                Document.batch == batch,
            )
            .order_by(asc("position"))
            .all()
        )
        # 验证文档是否存在
        if documents is None or len(documents) == 0:
            error_msg = "未找到文档"
            raise NotFoundException(error_msg)

        # 初始化文档状态列表
        documents_status = []
        # 遍历每个文档，收集状态信息
        for document in documents:
            upload_file = document.upload_file
            # 统计文档的分段总数
            segment_count = (
                self.db.session.query(func.count(Segment.id))
                .filter(
                    Segment.document_id == document.id,
                )
                .scalar()
            )
            # 统计已完成的分段数量
            completed_segment_count = (
                self.db.session.query(
                    func.count(Segment.id),
                )
                .filter(
                    Segment.document_id == document.id,
                    Segment.status == SegmentStatus.COMPLETED,
                )
                .scalar()
            )
            # 构建文档状态信息字典，包含基本信息和处理进度
            documents_status.append(
                {
                    "id": document.id,  # 文档ID
                    "name": document.name,  # 文档名称
                    "size": upload_file.size,  # 文件大小
                    "extension": upload_file.extension,  # 文件扩展名
                    "mime_type": upload_file.mime_type,  # MIME类型
                    "position": document.position,  # 文档位置
                    "segment_count": segment_count,  # 分段总数
                    "completed_segment_count": completed_segment_count,  # 已完成分段数
                    "error": document.error,  # 错误信息
                    "status": document.status,  # 文档状态
                    "processing_started_at": datetime_to_timestamp(  # 处理开始时间
                        document.processing_started_at,
                    ),
                    "parsing_completed_at": datetime_to_timestamp(  # 解析完成时间
                        document.parsing_completed_at,
                    ),
                    "splicing_completed_at": datetime_to_timestamp(  # 拼接完成时间
                        document.splitting_completed_at,
                    ),
                    "indexing_completed_at": datetime_to_timestamp(  # 索引完成时间
                        document.indexing_completed_at,
                    ),
                    "completed_at": datetime_to_timestamp(
                        document.completed_at,
                    ),  # 完成时间
                    "stopped_at": datetime_to_timestamp(
                        document.stopped_at,
                    ),  # 停止时间
                    "created_at": datetime_to_timestamp(
                        document.created_at,
                    ),  # 创建时间
                },
            )

        return documents_status
