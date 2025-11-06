import redis
from flask import Flask

redis_client = redis.Redis()


def init_app(app: Flask) -> None:
    """初始化Redis扩展

    Args:
        app: Flask应用实例

    Returns:
        None

    该函数会根据应用配置创建Redis连接池，支持SSL连接，并将Redis客户端实例存储在app.extensions中。

    """
    # 根据配置选择连接类型：普通连接或SSL连接
    connection_class = redis.Connection
    if app.config.get("REDIS_USE_SSL", False):
        connection_class = redis.SSLConnection

    # 创建Redis连接池，使用配置文件中的参数或默认值
    redis_client.connection_pool = redis.ConnectionPool(
        host=app.config.get("REDIS_HOST", "localhost"),  # Redis服务器地址
        port=app.config.get("REDIS_PORT", 6379),  # Redis服务器端口
        username=app.config.get("REDIS_USERNAME", ""),  # Redis用户名
        password=app.config.get("REDIS_PASSWORD", ""),  # Redis密码
        db=app.config.get("REDIS_DB", 0),  # Redis数据库编号
        encoding="utf-8",  # 编码格式
        encoding_errors="strict",  # 编码错误处理方式
        decode_responses=False,  # 是否自动解码响应
        connection_class=connection_class,  # 连接类型
    )

    # 将Redis客户端实例存储在Flask应用的extensions字典中
    app.extensions["redis"] = redis_client
