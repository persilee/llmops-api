import logging
import time
from uuid import UUID

from celery import shared_task
from flask import current_app

logger = logging.getLogger(__name__)


@shared_task
def test_task(task_id: UUID) -> str:
    """测试异步任务"""
    logger.info("休息 5 秒")
    time.sleep(5)
    logger.info("休息结束")
    logger.info("任务执行完成，id: %s", task_id)
    logger.info("配置信息: %s", current_app.config)

    return "OK"
