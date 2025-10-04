from flasgger import Swagger
from flask_migrate import Migrate
from injector import Binder, Module, singleton

from pkg.sqlalchemy import SQLAlchemy
from src.extension import db, migrate, swag


class ExtensionModule(Module):
    def configure(self, binder: Binder) -> None:
        """配置模块，绑定服务到注入器

        参数:
            binder (Binder): 依赖注入绑定器，用于注册服务

        功能:
            1. 将SQLAlchemy服务绑定到db实例，并设置为单例模式
            2. 将Migrate服务绑定到migrate实例
        """
        binder.bind(SQLAlchemy, to=db, scope=singleton)
        binder.bind(Migrate, to=migrate)
        binder.bind(Swagger, to=swag)
