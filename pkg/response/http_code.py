from enum import Enum

HTTP_STATUS_OK = 200
HTTP_STATUS_CREATED = 201
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_METHOD_NOT_ALLOWED = 405
HTTP_STATUS_INTERNAL_SERVER_ERROR = 500
HTTP_STATUS_SERVICE_UNAVAILABLE = 503
HTTP_STATUS_GATEWAY_TIMEOUT = 504


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
