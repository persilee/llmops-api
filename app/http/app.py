import dotenv
from flasgger import Swagger
from flask_migrate import Migrate

from config import Config
from pkg.sqlalchemy import SQLAlchemy
from src.router.router import Router
from src.server import Http

from .module import injector

# 加载环境变量
dotenv.load_dotenv()

# 创建一个Config类的实例对象
conf = Config()


# 创建Flask应用实例
app = Http(
    __name__,
    conf=conf,
    db=injector.get(SQLAlchemy),
    migrate=injector.get(Migrate),
    swag=injector.get(Swagger),
    router=injector.get(Router),
)

# 从Flask应用的扩展中获取Celery实例
celery = app.extensions["celery"]

if __name__ == "__main__":
    app.run(debug=True)
