import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Blueprint


class Redprint:
    def __init__(self, name) -> None:
        self.name = name
        self.mound = []

    def route(self, rule, **options: dict[str, Any]) -> Callable:
        def decorator(func) -> Callable:
            self.mound.append((func, rule, options))
            return func

        return decorator

    def register(self, bp, url_prefix=None) -> None:
        if url_prefix is None:
            url_prefix = f"/{self.name}"

        for func, rule, options in self.mound:
            endpoint = options.pop("endpoint", func.__name__)
            bp.add_url_rule(url_prefix + rule, endpoint, func, **options)


def register_with_class(
    obj: type[Any] | Any,
    bp: Blueprint,
    url_prefix: str | None = None,
) -> None:
    r"""将一个类中的路由方法注册到Flask蓝图(Blueprint)中。

    该函数会检查类中的所有方法，找出带有路由缓存(__rule_cache)的方法，
    并将这些方法的路由规则注册到指定的Flask蓝图中。

    Args:
        obj: 包含路由方法的类
        bp: Flask蓝图对象，用于注册路由
        url_prefix: URL前缀，会添加到所有路由规则的前面。默认为None

    Raises:
        AttributeError: 当类中不存在带有路由缓存的方法时
        ValueError: 当路由规则无效时

    Note:
        - 类中的方法需要通过装饰器设置__rule_cache属性才能被识别为路由方法
        - 如果options中没有指定endpoint，默认使用方法名作为endpoint
        - 特殊字符说明：
            \\t - 制表符
            \\r - 回车符
            \\n - 换行符

    """
    # 获取所有方法（包括实例方法）
    class_methods = inspect.getmembers(
        obj,
        predicate=inspect.isfunction,
    ) + inspect.getmembers(obj, predicate=inspect.ismethod)

    # 收集所有带有路由缓存的方法
    route_methods: list[tuple[Any, str, dict]] = []
    for _name, method in class_methods:
        if hasattr(method, "__rule_cache"):
            try:
                rule, options = method.__rule_cache[_name]  # noqa: SLF001
                route_methods.append((method, rule, options))
            except (KeyError, ValueError) as e:
                raise RouteConfigurationError(_name, str(e)) from e

    if not route_methods:
        raise AttributeError(ErrorMessages.NO_ROUTE_CACHE)

    # 注册路由
    for func, rule, options in route_methods:
        try:
            endpoint = options.pop("endpoint", func.__name__)
            full_url = f"{url_prefix}{rule}" if url_prefix else rule
            bp.add_url_rule(full_url, endpoint, func, **options)
        except Exception as e:
            raise RouteRegistrationError(func.__name__, str(e)) from e


def route(rule: str, **options: Any) -> Callable[[Callable], Callable]:
    r"""路由装饰器，用于将URL规则绑定到视图函数。

    Args:
        rule: URL规则字符串，必须以'/'开头
        **options: 额外的路由选项参数，支持以下选项：
            - methods: 允许的HTTP方法列表，如 ['GET', 'POST']
            - endpoint: 路由端点名称
            - defaults: 视图函数的默认参数字典
            - host: 域名限制
            - subdomain: 子域名限制
            - strict_slashes: 是否严格匹配URL末尾斜杠
            - provide_automatic_options: 是否自动提供OPTIONS方法

    Returns:
        装饰器函数，用于装饰视图函数

    Raises:
        ValueError: 当rule参数不是字符串或格式不正确时
        TypeError: 当options中包含不支持的参数类型时

    Note:
        该装饰器会在被装饰的函数上添加__rule_cache属性，
        用于存储URL规则和选项信息。
        特殊字符支持：
            \\t - 制表符
            \\r - 回车符
            \\n - 换行符

    Example:
        @route('/users/<int:user_id>', methods=['GET'])
        def get_user(user_id):
            return {'user_id': user_id}

    """
    # 验证rule参数
    if not isinstance(rule, str):
        raise RuleValidationError(str, type(rule).__name__)

    if not rule.startswith("/"):
        raise ValueError(ErrorMessages.INVALID_URL_PREFIX)

    # 验证options中的关键参数
    if "methods" in options:
        if not isinstance(options["methods"], (list, tuple)):
            raise MethodValidationError(ErrorMessages.INVALID_METHOD_TYPE)

        options["methods"] = [m.upper() for m in options["methods"]]

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: tuple[Any], **kwargs: dict[str, Any]) -> Any:
            return f(*args, **kwargs)

        # 初始化或更新路由缓存
        if not hasattr(wrapper, "__rule_cache"):
            wrapper.__rule_cache = {}  # noqa: SLF001

        wrapper.__rule_cache[f.__name__] = (rule, options)  # noqa: SLF001
        return wrapper

    return decorator


class RouteConfigurationError(ValueError):
    """Raised when there's an invalid route configuration."""

    def __init__(self, method_name: str, original_error: str) -> None:
        super().__init__(
            f"Invalid route configuration for method {method_name}: {original_error}",
        )


class RouteRegistrationError(ValueError):
    """Raised when route registration fails."""

    def __init__(self, func_name: str, original_error: str) -> None:
        super().__init__(f"Failed to register route for {func_name}: {original_error}")


class RuleValidationError(ValueError):
    """Raised when URL rule validation fails."""

    def __init__(self, expected_type: str, actual_type: str) -> None:
        super().__init__(f"rule must be a {expected_type}, got {actual_type}")


class MethodValidationError(TypeError):
    """Raised when methods parameter validation fails."""

    def __init__(self, expected_types: str) -> None:
        super().__init__(f"methods must be a {expected_types}")


class ErrorMessages:
    NO_ROUTE_CACHE = "No methods with route cache found in the class"
    INVALID_URL_PREFIX = "URL rule must start with '/'"
    INVALID_METHOD_TYPE = "list or tuple"
