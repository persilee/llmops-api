import dotenv
from flask_migrate import Migrate
from injector import Injector

from app.http.module import ExtensionModule
from config import Config
from internal.router.router import Router
from internal.server import Http
from pkg.sqlalchemy import SQLAlchemy

# 加载环境变量
dotenv.load_dotenv()

# 创建一个Config类的实例对象
conf = Config()

# 创建依赖注入器
injector = Injector([ExtensionModule])

app = Http(
    __name__,
    conf=conf,
    db=injector.get(SQLAlchemy),
    migrate=injector.get(Migrate),
    router=injector.get(Router),
)

if __name__ == "__main__":
    app.run(debug=True)
