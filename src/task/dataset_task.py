from uuid import UUID

from celery import shared_task


@shared_task
def delete_dataset(dataset_id: UUID) -> None:
    """异步删除知识库任务。

    Args:
        dataset_id (UUID): 要删除的知识库的唯一标识符

    Returns:
        None: 无返回值

    Note:
        这是一个异步任务，通过Celery执行。它会使用IndexingService来实际执行知识库的删除操作。

    """
    from app.http.module import injector
    from src.service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.delete_dataset(dataset_id)
