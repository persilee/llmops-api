from dataclasses import dataclass

from flask import Request
from injector import inject

from src.exception.exception import UnauthorizedException
from src.model.account import Account
from src.service.account_service import AccountService
from src.service.api_key_service import ApiKeyService
from src.service.jwt_service import JwtService


@inject
@dataclass
class Middleware:
    """中间件类，用于处理请求认证和授权。

    该类负责验证和解析传入的HTTP请求，支持多种认证方式：
    - JWT Token认证
    - API Key认证

    Attributes:
        jwt_service (JwtService): JWT令牌服务，用于处理JWT令牌的验证和解析
        account_service (AccountService): 账户服务，用于处理账户相关的业务逻辑
        api_key_service (ApiKeyService): API密钥服务，用于处理API密钥的验证

    """

    jwt_service: JwtService
    account_service: AccountService
    api_key_service: ApiKeyService

    def request_loader(self, request: Request) -> Account | None:
        """请求加载器，用于处理不同blueprint的请求认证

        Args:
            request (Request): Flask请求对象，包含请求头和blueprint信息

        Returns:
            Account | None: 返回认证成功的账户对象，如果blueprint不匹配则返回None

        Raises:
            UnauthorizedException: 当认证失败时抛出，包括：
                - JWT token无效或过期
                - API key无效或已禁用
                - 请求头中缺少Authorization或格式不正确

        处理流程：
            1. 检查请求的blueprint类型
            2. 对于llmops blueprint：
               - 验证JWT token
               - 解码token获取账户ID
               - 返回对应的账户信息
            3. 对于openapi blueprint：
               - 验证API key
               - 检查API key的有效性和激活状态
               - 返回对应的账户信息
            4. 其他blueprint返回None

        """
        if request.blueprint == "llmops":
            # 处理LLM Ops相关请求，使用JWT token认证
            access_token = self._validate_credential(request)

            # 解码JWT token获取payload
            payload = self.jwt_service.decode_token(access_token)
            account_id = payload.get("sub")

            # 根据账户ID获取并返回账户信息
            return self.account_service.get_account(account_id)
        if request.blueprint == "openapi":
            # 处理OpenAPI相关请求，使用API key认证
            api_key = self._validate_credential(request)

            # 根据API key获取API记录
            api_key_record = self.api_key_service.get_api_by_credential(api_key)

            # 验证API key的有效性和激活状态
            if not api_key_record or not api_key_record.is_active:
                error_msg = "无效的API密钥或API密钥已禁用"
                raise UnauthorizedException(error_msg)

            # 返回API key关联的账户信息
            return api_key_record.account
        # 其他blueprint类型返回None
        return None

    @classmethod
    def _validate_credential(cls, request: Request) -> str:
        """验证并提取请求中的认证凭证

        Args:
            request (Request): Flask请求对象，包含请求头信息

        Returns:
            str: 提取出的认证凭证（token或api_key）

        Raises:
            UnauthorizedException: 当以下情况发生时抛出：
                - 请求头中缺少Authorization字段
                - Authorization头格式不正确（缺少空格分隔符）
                - Authorization头不是Bearer类型

        """
        # 从请求头中获取Authorization字段
        auth_header = request.headers.get("Authorization")
        # 检查Authorization头是否存在
        if not auth_header:
            error_msg = "该接口需要认证，请提供Authorization头"
            raise UnauthorizedException(error_msg)

        # 检查Authorization头格式是否包含空格分隔符
        if " " not in auth_header:
            error_msg = "Authorization头格式错误，请提供Bearer token"
            raise UnauthorizedException(error_msg)

        # 分割Authorization头，获取认证类型和凭证
        auth_schema, credential = auth_header.split(None, 1)
        # 验证认证类型是否为Bearer
        if auth_schema.lower() != "bearer":
            error_msg = "Authorization头格式错误，请提供Bearer token"
            raise UnauthorizedException(error_msg)

        # 返回提取的凭证
        return credential
