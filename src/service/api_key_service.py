import secrets
from dataclasses import dataclass
from uuid import UUID

from injector import inject

from pkg.paginator.paginator import Paginator, PaginatorReq
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.exception.exception import NotFoundException
from src.model.account import Account
from src.model.api_key import ApiKey
from src.schemas.api_key_schema import CreateApiKeyReq
from src.service.base_service import BaseService


@inject
@dataclass
class ApiKeyService(BaseService):
    """API密钥服务类，负责处理API密钥的生成、创建、查询、更新和删除等操作。

    该类提供了完整的API密钥管理功能，包括：
    - 生成新的API密钥
    - 创建API密钥记录
    - 查询单个或分页查询API密钥
    - 更新API密钥信息
    - 删除API密钥
    """

    db: SQLAlchemy

    def generate_api_key(self, api_key_prefix: str = "llmops-vi/") -> str:
        """生成API密钥

        Args:
            api_key_prefix (str): API密钥前缀，默认为"llmops-vi/"

        Returns:
            str: 生成的API密钥字符串，由前缀和随机生成的安全字符串组成

        """
        return api_key_prefix + secrets.token_urlsafe(48)

    def create_api_key(self, req: CreateApiKeyReq, account: Account) -> ApiKey:
        """创建新的API密钥

        Args:
            req (CreateApiKeyReq): 创建API密钥的请求对象，包含is_active和remark字段
            account (Account): 要创建API密钥的账户对象

        Returns:
            ApiKey: 新创建的API密钥对象，包含生成的密钥字符串、账户ID、状态和备注信息

        """
        return self.create(
            ApiKey,
            account_id=account.id,
            api_key=self.generate_api_key(),
            is_active=req.is_active.data,
            remark=req.remark.data,
        )

    def get_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """获取API密钥

        Args:
            api_key_id (UUID): API密钥的唯一标识符
            account (Account): 账户对象，用于验证API密钥的所有权

        Returns:
            ApiKey: 返回找到的API密钥对象

        Raises:
            NotFoundException: 当API密钥不存在或不属于当前用户时抛出

        """
        api_key = self.get(ApiKey, api_key_id)
        if not api_key_id or api_key.account_id != account.id:
            error_msg = "API秘钥不存在或不属于当前用户"
            raise NotFoundException(error_msg)

        return api_key

    def update_api_key(
        self,
        api_key_id: UUID,
        account: Account,
        **kwargs: dict,
    ) -> ApiKey:
        """更新API密钥信息

        Args:
            api_key_id (UUID): 要更新的API密钥ID
            account (Account): 执行更新的账户信息
            **kwargs (dict): 要更新的字段和值

        Returns:
            ApiKey: 更新后的API密钥对象

        Raises:
            NotFoundException: 当API密钥不存在时抛出

        """
        api_key = self.get_api_key(api_key_id, account)

        self.update(api_key, **kwargs)

        return api_key

    def delete_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """删除指定的API密钥

        Args:
            api_key_id (UUID): 要删除的API密钥ID
            account (Account): 执行删除操作的账户对象

        Returns:
            ApiKey: 被删除的API密钥对象

        Raises:
            NotFoundException: 当API密钥不存在时抛出

        """
        api_key = self.get_api_key(api_key_id, account)

        self.delete(api_key)

        return api_key

    def get_api_keys_with_page(
        self,
        req: PaginatorReq,
        account: Account,
    ) -> tuple[list[ApiKey], Paginator]:
        """分页获取指定账户的API密钥列表

        Args:
            req: 分页请求参数，包含页码、每页数量等信息
            account: 账户信息，用于过滤该账户下的API密钥

        Returns:
            tuple[list[ApiKey], Paginator]: 返回一个元组，包含：
                - API密钥列表，按创建时间倒序排列
                - 分页器对象，包含分页相关信息

        """
        paginator = Paginator(db=self.db, req=req)

        api_keys = paginator.paginate(
            self.db.session.query(ApiKey)
            .filter(
                ApiKey.account_id == account.id,
            )
            .order_by(ApiKey.created_at.desc()),
        )

        return api_keys, paginator
