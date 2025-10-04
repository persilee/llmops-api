from dataclasses import field
from typing import Any

from pkg.response import HttpCode


class CustomException(Exception):
    """
    自定义异常类，用于处理应用程序中的异常情况。

    该类继承自Python内置的Exception类，提供了更丰富的异常信息处理能力，
    包括HTTP状态码、自定义错误消息和附加数据。

    主要功能：
    - 支持自定义错误消息
    - 支持附加任意类型的数据
    - 内置HTTP状态码支持

    示例用法：
        try:
            raise CustomException("操作失败", {"error": "invalid_input"})
        except CustomException as e:
            print(f"错误: {e.message}, 附加数据: {e.data}")

    构造函数参数：
        message (str, optional): 错误消息，默认为None
        data (Any, optional): 附加的错误数据，默认为None

    注意事项：
    - 该异常类主要用于API错误处理
    - data参数默认使用dict类型，但可以接受任意类型的数据
    """
    code: HttpCode = HttpCode.FAIL
    message: str = ""
    data: Any = field(default_factory=dict)

    def __init__(self, message: str = None, data: Any = None):
        super().__init__()
        self.message = message
        self.data = data


class FailException(CustomException):
    """
    自定义异常类FailException，继承自CustomException
    用于表示操作失败时的异常情况
    """
    pass  # 使用pass关键字表示该类暂时不添加额外的实现，保持父类的所有功能


class NotFoundException(CustomException):
    """自定义异常类：NotFoundException

    继承自CustomException，用于处理资源未找到的情况。
    包含一个类属性code，用于表示HTTP状态码。
    """
    code: HttpCode = HttpCode.NOT_FOUND  # 设置HTTP状态码为"未找到"(404)


class UnauthorizedException(CustomException):
    """自定义异常类：未授权异常
    当用户未经授权访问受保护的资源时抛出此异常
    """
    code: HttpCode = HttpCode.UNAUTHORIZED  # HTTP状态码：401 未授权


class ForbiddenException(CustomException):
    """
    自定义异常类：禁止访问异常
    当用户没有权限访问请求的资源时抛出此异常
    继承自CustomException基类
    """
    code: HttpCode = HttpCode.FORBIDDEN  # HTTP状态码设置为403，表示禁止访问


class InternalServerErrorException(CustomException):
    """
    内部服务器异常类
    继承自CustomException，用于表示服务器内部错误的异常情况
    """
    code: HttpCode = HttpCode.INTERNAL_SERVER_ERROR  # HTTP状态码设置为内部服务器错误(500)


class ValidateErrorException(CustomException):
    """
    自定义验证异常类
    用于处理数据验证失败时抛出的异常
    继承自CustomException基类
    """
    code: HttpCode = HttpCode.VALIDATE_ERROR  # 设置HTTP状态码为验证错误码
