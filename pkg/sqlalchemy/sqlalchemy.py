from contextlib import contextmanager

from flask_sqlalchemy import SQLAlchemy as _SQLAlchemy


class SQLAlchemy(_SQLAlchemy):
    """
    SQLAlchemy类，继承自_SQLAlchemy
    提供数据库操作的相关功能，包括自动提交事务的上下文管理器
    """

    @contextmanager
    def auto_commit(self):
        """
        自动提交事务的上下文管理器
        使用上下文管理器确保数据库操作的原子性
        成功则提交，异常则回滚
        """
        try:
            yield  # 执行被上下文管理器包裹的代码块
            self.session.commit()  # 无异常则提交事务
        except Exception as e:
            self.session.rollback()  # 发生异常则回滚事务
            raise e  # 重新抛出异常
