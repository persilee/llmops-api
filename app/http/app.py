import dotenv
from flasgger import Swagger
from flask_login import LoginManager
from flask_migrate import Migrate

from config import Config
from pkg.sqlalchemy import SQLAlchemy
from src.middleware.middleware import Middleware
from src.router.router import Router
from src.server import Http
from src.server.http import HttpConfig

from .module import injector

# 加载环境变量
dotenv.load_dotenv()

# 创建一个Config类的实例对象
conf = Config()

# 创建一个HttpConfig类的实例对象
http_config = HttpConfig(
    conf=conf,
    db=injector.get(SQLAlchemy),
    migrate=injector.get(Migrate),
    login_manager=injector.get(LoginManager),
    middleware=injector.get(Middleware),
    swag=injector.get(Swagger),
    router=injector.get(Router),
)

# 创建Flask应用实例
app = Http(__name__, http_config=http_config)

# 从Flask应用的扩展中获取Celery实例
celery = app.extensions["celery"]

if __name__ == "__main__":
    app.run(debug=True)
