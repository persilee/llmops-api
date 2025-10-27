from collections.abc import Generator
from typing import Any

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import scoped_session, sessionmaker

from app.http.app import app as _app
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.extension.database_extension import db as _db
from src.server.http import Http


@pytest.fixture(scope="module")
def app() -> Http:
    """创建Flask应用实例的fixture。

    这个fixture将Flask应用配置为测试模式，并返回应用实例。
    测试模式下，应用会启用错误处理和调试功能，便于测试过程中发现问题。

    Returns:
        Http: 配置为测试模式的Flask应用实例

    """
    _app.config["TESTING"] = True

    return _app


@pytest.fixture(scope="module")
def client(app) -> Generator[FlaskClient, Any, None]:
    """创建Flask测试客户端的fixture。

    这个fixture设置Flask应用为测试模式，并创建一个测试客户端实例。
    使用module级别的scope，确保在整个测试模块中只创建一次客户端。

    Returns:
        Generator[FlaskClient, Any, None]: 生成Flask测试客户端的生成器

    """
    with app.test_client() as client:
        yield client


@pytest.fixture
def db(app) -> Generator[SQLAlchemy, Any, None]:
    """创建测试数据库会话的fixture。

    这个fixture创建一个独立的数据库连接和事务，为每个测试提供一个干净的数据库环境。
    它使用事务回滚来确保测试之间的隔离性，测试完成后所有更改都会被撤销。

    Args:
        app: Flask应用实例，由app fixture提供

    Yields:
        SQLAlchemy: 配置好的数据库实例，可以在测试中使用

    Note:
        - 使用scoped_session确保线程安全
        - 每个测试都会在一个独立的事务中运行
        - 测试完成后会自动回滚所有更改
        - 会自动清理数据库连接和会话

    """
    with app.app_context():  # 确保在Flask应用上下文中执行数据库操作
        # 创建数据库连接
        connection = _db.engine.connect()
        # 开始一个新的事务
        transaction = connection.begin()

        # 创建会话工厂，绑定到当前连接
        session_factory = sessionmaker(bind=connection)
        # 使用scoped_session确保线程安全
        session = scoped_session(session_factory)
        # 将创建的会话设置为数据库的当前会话
        _db.session = session

        # 将数据库实例提供给测试使用
        yield _db

        # 测试完成后，回滚事务以撤销所有更改
        transaction.rollback()
        # 关闭数据库连接
        connection.close()
        # 移除会话，清理资源
        session.remove()
