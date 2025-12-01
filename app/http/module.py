from flasgger import Swagger
from flask_login import LoginManager
from flask_migrate import Migrate
from injector import Binder, Injector, Module, singleton
from redis import Redis

from pkg.sqlalchemy import SQLAlchemy
from src.extension import db, migrate, redis_client, swag
from src.extension.login_extension import login_manager


class ExtensionModule(Module):
    def configure(self, binder: Binder) -> None:
        """配置模块，绑定服务到注入器

        参数:
            binder (Binder): 依赖注入绑定器，用于注册服务

        功能:
            1. 将SQLAlchemy服务绑定到db实例，并设置为单例模式
            2. 将Migrate服务绑定到migrate实例
            3. 将Swagger服务绑定到swag实例
            4. 将Redis服务绑定到redis_client实例，并设置为单例模式
        """
        binder.bind(SQLAlchemy, to=db, scope=singleton)
        binder.bind(Migrate, to=migrate)
        binder.bind(Swagger, to=swag)
        binder.bind(Redis, to=redis_client, scope=singleton)
        binder.bind(LoginManager, to=login_manager)


# 创建依赖注入器
injector = Injector([ExtensionModule])
