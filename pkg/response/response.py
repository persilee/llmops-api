from dataclasses import dataclass, field
from typing import Any

from flask import Response as FlaskResponse
from flask import jsonify

from pkg.response.http_code import HttpCode


@dataclass
class Response:
    """API响应封装类

    用于统一API响应格式，包含状态码、消息和数据

    Attributes:
        code (HttpCode): HTTP状态码，默认为SUCCESS
        message (str): 响应消息，默认为空字符串
        data (Any): 响应数据，默认为空字典

    """

    code: HttpCode = HttpCode.SUCCESS
    message: str = ""
    data: Any = field(default_factory=dict)


def json(data: Response = None) -> FlaskResponse:
    """将响应数据转换为 JSON 格式并返回

    Args:
        data (Response, optional): 需要转换为 JSON 格式的响应数据。默认为 None。

    Returns:
        tuple: 包含 JSON 格式的响应数据和 HTTP 状态码 200 的元组

    Note:
        - 使用 jsonify 函数将输入数据转换为 JSON 格式
        - 固定返回 HTTP 状态码 200 表示请求成功
        - 支持处理特殊字符如 //t (制表符), //r (回车符) 和 //n (换行符)

    """
    return jsonify(data)


def success_json(data: Any | None = None) -> Response:
    """返回一个表示成功的 JSON 响应。

    该函数创建一个包含成功状态码、空消息和可选数据的 Response 对象，
    并将其转换为 JSON 格式返回。

    参数:
        data (Any, optional): 要包含在响应中的数据。默认为 None。

    返回:
        json: 包含成功响应的 JSON 对象。

    示例:
        >>> success_json({"user": "John"})
        '{"code": 200, "message": "", "data": {"user": "John"}}'
    """
    return json(Response(code=HttpCode.SUCCESS, message="", data=data))


def fail_json(data: Any | None = None) -> Response:
    """返回一个表示失败的JSON响应。

    该函数接收一个可选的数据参数，构造一个包含失败状态码的Response对象，
    并将其转换为JSON格式返回。默认情况下，消息字段为空字符串。

    参数:
        data (Any, optional): 要包含在响应中的数据。默认为None。

    返回:
        json: 包含失败状态码和提供数据的JSON格式响应。

    注意:
        - 使用HttpCode.FAIL作为失败状态码
        - 消息字段默认为空字符串
        - 支持通过data参数传入任意类型的数据
    """
    return json(Response(code=HttpCode.FAIL, message="", data=data))


def validate_error_json(errors: dict | None) -> Response:
    """将验证错误信息格式化为 JSON 响应

    该函数接收一个包含验证错误的字典，提取第一个错误消息，
    并将其包装成一个标准的 JSON 响应格式返回。

    Args:
        errors (dict, optional): 包含验证错误的字典。默认为 None。
            字典的键是字段名，值是该字段的错误消息列表。
            例如: {"username": ["用户名已存在"], "email": ["邮箱格式不正确"]}

    Returns:
        json: 包含错误信息的 JSON 响应对象，格式为：
            {
                "code": HttpCode.VALIDATE_ERROR,
                "message": str,  # 第一个错误消息
                "data": dict    # 完整的错误字典
            }

    Note:
        - 如果 errors 为 None 或空字典，message 将为空字符串
        - 使用 HttpCode.VALIDATE_ERROR 作为错误代码
        - 原始的错误字典会完整保存在返回的 data 字段中

    """
    if not errors:  # 添加空字典检查
        return json(
            Response(code=HttpCode.VALIDATE_ERROR, message="验证失败", data=errors),
        )
    first_key = next(iter(errors))
    msg = errors[first_key][0] if first_key is not None else ""

    return json(Response(code=HttpCode.VALIDATE_ERROR, message=msg, data=errors))


def message_json(code: HttpCode = None, message: str = "") -> Response:
    """将响应信息转换为JSON格式

    Args:
        code (HttpCode, optional): HTTP状态码. Defaults to None.
        message (str, optional): 响应消息内容. Defaults to "".

    Returns:
        json: 包含响应信息的JSON对象，格式为：
            {
                "code": HttpCode,
                "message": str,
                "data": dict
            }

    """
    return json(Response(code=code, message=message, data={}))


def success_message_json(message: str = "") -> Response:
    """生成一个表示操作成功的JSON消息。

    该函数用于创建一个包含成功状态码和自定义消息的JSON响应。
    成功状态码使用HttpCode.SUCCESS枚举值。

    Args:
        message (str, optional): 要包含在响应中的自定义消息。默认为空字符串。

    Returns:
        dict: 包含成功状态码和消息的JSON格式字典。

    Note:
        返回的JSON格式为：
        {
            "code": HttpCode.SUCCESS,
            "message": message
        }
        其中HttpCode.SUCCESS表示操作成功。

    Example:
        >>> success_message_json("操作成功")
        {'code': 200, 'message': '操作成功'}

    """
    return message_json(code=HttpCode.SUCCESS, message=message)


def fail_message_json(message: str = "") -> Response:
    """生成表示失败的 JSON 格式消息

    该函数用于创建一个表示操作失败的 JSON 格式消息对象，使用预设的失败状态码。

    参数:
        message (str, optional): 失败消息内容。默认为空字符串。

    返回:
        dict: 包含失败状态码和消息的 JSON 格式字典对象

    示例:
        >>> fail_message_json("操作失败")
        {'code': 500, 'message': '操作失败'}
    """
    return message_json(code=HttpCode.FAIL, message=message)


def not_found_message_json(message: str = "") -> Response:
    """生成一个表示"未找到"的JSON格式消息响应。

    该函数用于创建一个标准的HTTP 404 Not Found响应，以JSON格式返回。
    可以自定义返回的消息内容。

    Args:
        message (str, optional): 自定义的消息内容。默认为空字符串。

    Returns:
        dict: 包含HTTP状态码和消息的JSON格式字典。

    Note:
        - 使用HttpCode.NOT_FOUND作为状态码
        - 返回格式符合message_json函数的规范

    """
    return message_json(code=HttpCode.NOT_FOUND, message=message)


def unauthorized_message_json(message: str = "") -> Response:
    """生成未授权访问的JSON格式错误消息。

    该函数用于创建一个表示未授权访问的JSON格式错误响应消息。它使用预定义的HTTP状态码
    和自定义的错误消息来构建响应。

    Args:
        message (str, optional): 自定义错误消息。默认为空字符串。

    Returns:
        dict: 包含未授权错误信息的JSON格式字典，包含以下键：
            - code: HTTP状态码（未授权）
            - message: 错误描述信息

    Examples:
        >>> unauthorized_message_json("请先登录")
        {'code': 401, 'message': '请先登录'}

    Note:
        - 该函数依赖message_json函数来构建最终的JSON响应
        - 使用HttpCode.UNAUTHORIZED作为默认的HTTP状态码

    """
    return message_json(code=HttpCode.UNAUTHORIZED, message=message)


def forbidden_message_json(message: str = "") -> Response:
    """生成包含禁止访问信息的JSON响应消息。

    该函数用于创建一个表示禁止访问(403 Forbidden)的JSON格式响应消息。
    使用HttpCode.FORBIDDEN作为状态码，并可以自定义错误消息。

    参数:
        message (str, optional): 错误消息内容，默认为空字符串

    返回:
        dict: 包含错误码和错误消息的JSON格式字典

    示例:
        >>> forbidden_message_json("Access denied")
        {'code': 403, 'message': 'Access denied'}
    """
    return message_json(code=HttpCode.FORBIDDEN, message=message)
