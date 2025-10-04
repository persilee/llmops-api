from enum import Enum


class HttpCode(str, Enum):
    # 成功状态
    SUCCESS = "success"
    # 失败状态
    FAIL = "fail"
    # 资源未找到状态
    NOT_FOUND = "not_found"
    # 未授权状态
    UNAUTHORIZED = "unauthorized"
    # 禁止访问状态
    FORBIDDEN = "forbidden"
    # 验证错误状态
    VALIDATE_ERROR = "validate_error"
    # 服务器内部错误状态
    INTERNAL_SERVER_ERROR = "internal_server_error"
    # 服务不可用状态
    SERVICE_UNAVAILABLE = "service_unavailable"
