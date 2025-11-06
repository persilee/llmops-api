DEFAULT_CONFIG = {
    # CSRF（跨站请求伪造）保护
    "WTF_CSRF_ENABLED": "False",
    # 数据库配置
    "SQLALCHEMY_DATABASE_URI": "",
    "SQLALCHEMY_POOL_SIZE": 30,
    "SQLALCHEMY_POOL_RECYCLE": 3600,
    "SQLALCHEMY_ECHO": "True",
    # Redis配置
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_DB": "0",
    "REDIS_USE_SSL": "False",
}
