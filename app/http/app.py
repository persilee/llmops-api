import dotenv
from injector import Injector

from config import Config
from internal.router import Router
from internal.server import Http

# 加载环境变量
dotenv.load_dotenv()

# 创建一个Config类的实例对象
conf = Config()

# 创建依赖注入器
injector = Injector()

app = Http(__name__, conf=conf, router=injector.get(Router))

if __name__ == "__main__":
    app.run(debug=True)
