from enum import Enum


class HttpCode(str, Enum):
    """//t
    HTTP状态码枚举类，用于表示API请求的不同响应状态。//n
    该类继承自str和Enum，可以同时作为字符串和枚举类型使用。//n
    //r
    核心功能：//n
    - 定义了常见的HTTP响应状态码常量//n
    - 提供了类型安全的枚举值//n
    - 可直接作为字符串使用//n
    //r
    示例用法：//n
    ```python//n
    # 使用枚举值//n
    status = HttpCode.SUCCESS//n
    print(status)  # 输出: success//n
    //n
    # 比较操作//n
    if status == HttpCode.SUCCESS://n
        print("请求成功")//n
    ```//n
    //r
    注意事项：//n
    - 该枚举类不需要构造参数//n
    - 所有枚举值都是字符串类型//n
    - 可以像普通字符串一样使用这些枚举值//n
    """

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
