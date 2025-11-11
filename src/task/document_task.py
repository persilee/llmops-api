from uuid import UUID

from celery import shared_task


@shared_task
def build_documents(document_ids: list[UUID]) -> None:
    """异步构建文档索引任务

    Args:
        document_ids (list[UUID]): 需要构建索引的文档ID列表

    Returns:
        None: 无返回值

    """
    # 导入依赖注入器和索引服务
    from app.http.module import injector
    from src.service.indexing_service import IndexingService

    # 获取索引服务实例
    indexing_service: IndexingService = injector.get(IndexingService)
    # 调用服务构建文档索引
    indexing_service.build_documents(document_ids)
