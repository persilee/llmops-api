import os
from pathlib import Path
from typing import Any

import yaml
from flasgger import Swagger
from flask import Flask
from flask_migrate import Migrate

from config import Config, swagger_config, swagger_template
from pkg.response import HttpCode, Response, json
from pkg.sqlalchemy import SQLAlchemy
from src.exception import CustomException
from src.router import Router
from src.schemas import schemas


class Http(Flask):
    """Http服务"""

    def __init__(
        self,
        *args: str,
        conf: Config,
        db: SQLAlchemy,
        migrate: Migrate,
        swag: Swagger,
        router: Router,
        **kwargs: dict[str, Any],
    ) -> None:
        # 调用父类的构造方法，传递所有位置参数和关键字参数
        super().__init__(*args, **kwargs)

        # 从配置对象中加载配置
        # from_object()方法会从给定的配置对象中加载配置项
        # conf参数是一个配置对象，可以是Python模块、类或字典
        self.config.from_object(conf)

        # 注册异常处理函数，
        # 将所有异常(Exception)类型的错误都交给_register_error_handler方法处理
        self.register_error_handler(Exception, self._register_error_handler)

        # 初始化数据库
        db.init_app(self)
        migrate.init_app(self, db, directory="internal/migration")

        # 初始化Swagger
        self._init_swagger(swag, schemas)

        # 初始化路由器
        self.router = router

        # 将当前路由实例注册到路由器中
        router.register_route(self)

    def _register_error_handler(self, error: Exception) -> Response:
        """注册错误处理器，根据不同类型的异常返回相应的错误响应。

        Args:
            error (Exception): 捕获的异常对象

        Returns:
            json: 包含错误信息的JSON响应

        Note:
            - 对于CustomException类型的异常，使用异常中定义的code、message和data
            - 在调试模式或开发环境下，返回详细的调试信息
            - 在生产环境下，只返回基本的错误信息

        """
        if isinstance(error, CustomException):
            response = Response(
                code=error.code,
                message=error.message,
                data=error.data if error.data else {},
            )
            return json(response)

        if self.debug or os.getenv("FLASK_ENV") == "development":
            response = Response(
                code=HttpCode.FAIL,
                message=f"Debug error: {error!s}",
                data={"debug": True, "error_type": type(error).__name__},
            )
            return json(response)
        response = Response(
            code=HttpCode.FAIL,
            message=str(error),
            data={},
        )
        return json(response)

    def _init_swagger(
        self,
        swag: Swagger,
        schemas: dict[str, Any] | None = None,
    ) -> None:
        # 加载公共定义
        with Path.open("docs/common_definitions.yaml", encoding="utf-8") as f:
            common_defs = yaml.safe_load(f)
        template = swagger_template
        template["definitions"].update(common_defs.get("definitions", {}))

        # 加载数据类定义
        if schemas:
            for name, schema in schemas.items():
                template["definitions"][name] = schema

        swag.config = swagger_config
        swag.template = template
        swag.init_app(self)
