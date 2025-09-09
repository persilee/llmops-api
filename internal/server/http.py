from flask import Flask

from config import Config
from internal.router import Router


class Http(Flask):
    """Http服务"""

    def __init__(self, *args, conf: Config, router: Router, **kwargs):
        super().__init__(*args, **kwargs)
        # 注册路由
        router.register_route(self)  # 将当前路由实例注册到路由器中
        # 从配置对象中加载配置
        # from_object()方法会从给定的配置对象中加载配置项
        # conf参数是一个配置对象，可以是Python模块、类或字典
        self.config.from_object(conf)
