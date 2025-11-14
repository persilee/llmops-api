from typing import Any, TypeVar

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.exception.exception import FailException

T = TypeVar("T")


class BaseService:
    """基础服务类，提供基本的数据库操作方法"""

    db: SQLAlchemy

    def create(self, model: T, **kwargs: dict) -> T:
        """创建新记录

        Args:
            model: 数据模型类
            **kwargs: 模型字段和对应的值

        Returns:
            Any: 创建的模型实例

        """
        with self.db.auto_commit():
            model_instance = model(**kwargs)
            self.db.session.add(model_instance)

        return model_instance

    def delete(self, model_instance: T) -> T:
        """删除记录

        Args:
            model_instance: 要删除的模型实例

        Returns:
            Any: 被删除的模型实例

        """
        with self.db.auto_commit():
            self.db.session.delete(model_instance)

        return model_instance

    def update(self, model_instance: T, **kwargs: dict) -> T:
        """更新记录

        Args:
            model_instance: 要更新的模型实例
            **kwargs: 要更新的字段和对应的值

        Returns:
            Any: 更新后的模型实例

        Raises:
            FailException: 当要更新的字段不存在时抛出异常

        """
        with self.db.auto_commit():
            for field, value in kwargs.items():
                if hasattr(model_instance, field):
                    setattr(model_instance, field, value)
                else:
                    error_msg = f"更新字段不存在: {field}"
                    raise FailException(error_msg)

        return model_instance

    def get(self, model: T, primary_key: Any) -> T | None:
        """根据主键获取记录

        Args:
            model: 数据模型类
            primary_key: 主键值

        Returns:
            Any | None: 找到的模型实例，如果不存在则返回None

        """
        return self.db.session.get(model, primary_key)
