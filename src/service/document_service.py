import logging
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from pkg.sqlalchemy import SQLAlchemy
from src.entity.dataset_entity import ProcessType
from src.entity.upload_file_entity import ALLOWED_DOCUMENT_EXTENSION
from src.exception.exception import FailException, ForbiddenException
from src.model.dataset import Dataset, Document, ProcessRule
from src.model.upload_file import UploadFile
from src.service.base_service import BaseService
from src.task.document_task import build_documents

logger = logging.getLogger(__name__)


@inject
@dataclass
class DocumentService(BaseService):
    db: SQLAlchemy

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
