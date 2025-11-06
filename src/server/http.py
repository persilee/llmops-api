import logging
import os
from pathlib import Path
from typing import Any

import yaml
from flasgger import Swagger
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from config import Config, swagger_config, swagger_template
from pkg.response import HttpCode, Response, json
from pkg.sqlalchemy import SQLAlchemy
from src.exception import CustomException
from src.extension import logging_extension, redis_extension
from src.router import Router
from src.schemas import swag_schemas


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
        # 获取模块特定的 logger 对象
        self.logger = logging.getLogger(__name__)

        # 从配置对象中加载配置
        # from_object()方法会从给定的配置对象中加载配置项
        # conf参数是一个配置对象，可以是Python模块、类或字典
        self.config.from_object(conf)

        # 注册异常处理函数，
        # 将所有异常(Exception)类型的错误都交给_register_error_handler方法处理
        self.register_error_handler(Exception, self._register_error_handler)

        # 初始化数据库
        db.init_app(self)
        migrate.init_app(self, db, directory="src/migration")

        # 初始化 Redis
        redis_extension.init_app(self)

        # 初始化日志记录
        logging_extension.init_app(self)

        # 配置跨域
        CORS(
            self,
            resources={
                r"/*": {
                    "origins": "*",
                    "supports_credentials": True,
                    "methods": ["GET", "POST"],
                    "allow_headers": ["Content-Type"],
                },
            },
        )

        # 初始化Swagger
        self._init_swagger(swag, swag_schemas)

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
        # 记录错误日志
        self.logger.error("Error: %s", error)

        # 根据异常类型返回相应的错误响应
        if isinstance(error, CustomException):
            response = Response(
                code=error.code,
                message=error.message,
                data=error.data if error.data else {},
            )
            return json(response)

        # 如果异常不是CustomException类型，则返回通用错误响应
        if self.debug or os.getenv("FLASK_ENV") == "development":
            raise error
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
        with Path.open("docs/components.yaml", encoding="utf-8") as f:
            common_defs = yaml.safe_load(f)
        template = swagger_template
        template["components"].update(common_defs.get("components", {}))

        # 加载数据类定义
        if schemas:
            for name, schema in schemas.items():
                template["components"]["schemas"][name] = schema

        # 配置swagger标题和版本
        self.config["SWAGGER"] = {
            "title": "LLMops API",
            "openapi": "3.0.4",
        }

        # 初始化swagger
        swag.config = swagger_config
        swag.template = template
        swag.init_app(self)
