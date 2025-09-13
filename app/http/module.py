from injector import Module, Binder, singleton

from internal.extension.database_extension import db
from pkg.sqlalchemy import SQLAlchemy


class ExtensionModule(Module):
    def configure(self, binder: Binder):
        """配置依赖注入绑定关系。

        将SQLAlchemy实例绑定到数据库连接对象db上，以便在需要时可以通过依赖注入获取数据库连接。

        Args:
            binder (Binder): 依赖注入绑定器对象，用于建立类型和实例之间的映射关系。
        """
        binder.bind(SQLAlchemy, to=db, scope=singleton)
