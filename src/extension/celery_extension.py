from typing import Any

from celery import Celery, Task
from flask import Flask


def init_app(app: Flask) -> None:
    """初始化Celery扩展，将其集成到Flask应用中"""

    class FlaskTask(Task):
        """自定义任务类，确保任务在Flask应用上下文中执行"""

        def __call__(self, *args: tuple, **kwargs: dict) -> Any:
            """重写Task的__call__方法，在执行任务时激活Flask应用上下文"""
            with app.app_context():
                return self.run(*args, **kwargs)

    # 创建Celery实例，使用Flask应用名称作为标识，并指定自定义的任务类
    celery_app = Celery(app.name, task_cls=FlaskTask)
    # 从Flask配置中加载Celery配置
    celery_app.config_from_object(app.config["CELERY"])
    # 将此Celery实例设置为默认实例
    celery_app.set_default()

    # 将Celery实例存储在Flask应用的extensions字典中，方便后续访问
    app.extensions["celery"] = celery_app
