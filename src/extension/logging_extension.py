import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from flask import Flask


def init_app(app: Flask) -> None:
    """初始化Flask应用的日志系统

    Args:
        app: Flask应用实例

    """
    # 创建日志文件夹路径
    log_folder = Path.cwd() / "storage" / "logs"
    # 如果日志文件夹不存在，则创建它（包括所有必需的父目录）
    if not log_folder.exists():
        log_folder.mkdir(parents=True)

    # 设置日志文件路径
    log_file = log_folder / "app.log"

    # 创建定时轮转的文件处理器
    # when="midnight": 每天午夜轮转日志文件
    # interval=1: 轮转间隔为1天
    # backupCount=30: 保留30个历史日志文件
    # encoding="utf-8": 使用UTF-8编码写入日志
    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )

    # 设置日志格式
    # 格式包含：时间戳（精确到毫秒）、文件名、函数名、行号、日志级别、消息
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s "
        "line:%(lineno)d [%(levelname)s] %(message)s",
    )

    # 设置文件处理器的日志级别为DEBUG
    handler.setLevel(logging.DEBUG)
    # 为文件处理器设置日志格式
    handler.setFormatter(formatter)
    # 将文件处理器添加到根日志记录器
    logging.getLogger().addHandler(handler)

    # 如果是开发环境或调试模式，添加控制台日志处理器
    if app.debug or os.getenv("FLASK_ENV") == "development":
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        # 为控制台处理器设置相同的日志格式
        console_handler.setFormatter(formatter)
        # 将控制台处理器添加到根日志记录器
        logging.getLogger().addHandler(console_handler)
