import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import select

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.tools.api_tool.entities.openapi_schema import OpenAPISchema
from src.core.tools.providers.api_provider_manager import ApiProviderManager
from src.exception.exception import NotFoundException, ValidateErrorException
from src.model.api_tool import ApiTool, ApiToolProvider
from src.schemas.api_tool_schema import (
    CreateApiToolReq,
    GetApiToolProvidersWithPageReq,
    UpdateApiToolProviderReq,
)
from src.service.base_service import BaseService


@inject
@dataclass
class ApiToolService(BaseService):
    """API工具服务类，用于处理OpenAPI规范相关的操作"""

    db: SQLAlchemy
    api_provider_manager: ApiProviderManager

    def update_api_tool_provider(
        self,
        provider_id: UUID,
        req: UpdateApiToolProviderReq,
    ) -> None:
        """更新API工具提供者信息

        Args:
            provider_id: API工具提供者ID
            req: 更新API工具提供者的请求对象，包含名称、OpenAPI schema、
            图标和请求头等信息

        Raises:
            ValidateErrorException: 当API工具提供者不存在或名称重复时抛出

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 查询并验证API工具提供者是否存在且属于当前账户
        provider = self.get(ApiToolProvider, provider_id)
        if not provider or str(provider.account_id) != account_id:
            error_msg = f"未找到ID为{provider_id}的API工具提供者"
            raise ValidateErrorException(error_msg)

        # 解析OpenAPI schema字符串为结构化对象
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        # 检查是否存在同名的API工具提供者
        check_api_tool_provider = (
            self.db.session.query(ApiToolProvider)
            .filter(
                ApiToolProvider.account_id == account_id,
                ApiToolProvider.name == req.name.data,
                ApiToolProvider.id != provider_id,
            )
            .one_or_none()
        )
        if check_api_tool_provider:
            error_msg = f"名称为{req.name.data}的API工具提供者已存在"
            raise ValidateErrorException(error_msg)

        # 使用事务更新API工具提供者和相关API工具
        with self.db.auto_commit():
            # 删除原有的API工具记录
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == provider.id,
                ApiTool.account_id == account_id,
            ).delete()

        # 更新API工具提供者的基本信息
        self.update(
            provider,
            name=req.name.data,
            icon=req.icon.data,
            headers=req.headers.data,
            description=openapi_schema.description,
            openapi_schema=req.openapi_schema.data,
        )

        # 遍历OpenAPI schema中的所有路径和方法，创建新的API工具记录
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                # 为每个API方法创建对应的API工具记录
                self.create(
                    ApiTool,
                    account_id=account_id,
                    provider_id=provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    # 组合服务器基础URL和路径形成完整的API端点
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    def get_api_tool_providers_with_page(
        self,
        req: GetApiToolProvidersWithPageReq,
    ) -> tuple[list[Any], Paginator]:
        """获取API工具提供者分页列表。

        Args:
            req: 获取API工具提供者分页列表的请求对象，包含分页参数和搜索条件

        Returns:
            tuple[list[Any], Paginator]: 返回一个元组，包含：
                - API工具提供者列表
                - 分页器对象，包含分页相关信息

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 初始化分页器，用于处理分页逻辑
        paginator = Paginator(db=self.db, req=req)
        # 构建基础过滤条件，只查询当前账户的API工具提供者
        stmt = select(ApiToolProvider).where(ApiToolProvider.account_id == account_id)
        # 如果存在搜索关键词，添加名称模糊匹配的过滤条件
        if req.search_word.data:
            stmt = stmt.where(ApiToolProvider.name.ilike(f"%{req.search_word.data}%"))
        # 添加过滤条件并按创建时间倒序排序
        stmt = stmt.order_by(ApiToolProvider.created_at.desc())
        # 执行分页查询
        api_tool_providers = paginator.paginate(stmt)

        # 返回查询结果和分页器对象
        return api_tool_providers, paginator

    def delete_api_tool_provider(self, provider_id: UUID) -> None:
        """删除API工具提供者及其相关的API工具

        Args:
            provider_id: API工具提供者的唯一标识符

        Raises:
            NotFoundException: 当API工具提供者不存在或不属于当前账户时抛出

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"
        # 查询API工具提供者
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        # 验证API工具提供者是否存在且属于当前账户
        if api_tool_provider is None or str(api_tool_provider.account_id) != account_id:
            error_msg = f"API工具提供者 {provider_id} 不存在"
            raise NotFoundException(error_msg)

        # 使用自动提交事务删除相关数据
        with self.db.auto_commit():
            # 删除该提供者下的所有API工具
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == provider_id,
                ApiTool.account_id == account_id,
            ).delete()
            # 删除API工具提供者
            self.db.session.delete(api_tool_provider)

    def get_api_tool(self, provider_id: UUID, tool_name: str) -> ApiTool:
        """根据提供者ID和工具名称获取API工具。

        Args:
            provider_id (UUID): API工具提供者的唯一标识符
            tool_name (str): API工具的名称

        Returns:
            ApiTool: 查询到的API工具对象

        Raises:
            ValidateErrorException: 当API工具不存在或无权限访问时抛出

        Note:
            当前使用硬编码的账户ID进行权限验证，实际应用中应该从认证信息中获取

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 使用SQLAlchemy查询API工具
        api_tool = (
            self.db.session.query(ApiTool)  # 创建ApiTool模型的查询对象
            .filter_by(
                provider_id=provider_id,  # 根据提供者ID筛选
                name=tool_name,  # 根据工具名称筛选
            )
            .one_or_none()  # 返回单个结果或None
        )

        # 验证API工具是否存在且属于当前账户
        if api_tool is None or str(api_tool.account_id) != account_id:
            error_msg = f"API工具 {tool_name} 不存在"  # 构造错误信息
            raise NotFoundException(error_msg)  # 抛出验证错误异常

        # 返回查询到的API工具对象
        return api_tool

    def get_api_tool_provider(self, provider_id: UUID) -> ApiToolProvider:
        """根据提供者ID获取API工具提供者信息。

        Args:
            provider_id (UUID): API工具提供者的唯一标识符

        Returns:
            ApiToolProvider: API工具提供者对象

        Raises:
            ValidateErrorException: 当API工具提供者不存在或不属于当前账户时抛出

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 根据provider_id查询API工具提供者
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        # 验证API工具提供者是否存在且属于当前账户
        if api_tool_provider is None or str(api_tool_provider.account_id) != account_id:
            # 构造错误信息
            error_msg = f"API工具提供者不存在: {provider_id}"
            # 抛出验证错误异常
            raise NotFoundException(error_msg)

        # 返回查询到的API工具提供者
        return api_tool_provider

    @classmethod
    def _validate_dict_format(cls, data: Any) -> None:
        """验证数据是否为字典类型

        Args:
            data: 需要验证的数据

        Raises:
            ValidateErrorException: 当数据不是字典类型时抛出

        """
        if not isinstance(data, dict):
            error_msg = "数据必须是一个字典类型"
            raise ValidateErrorException(error_msg)

    @classmethod
    def parse_openapi_schema(cls, openapi_schema_srt: str) -> OpenAPISchema:
        """解析OpenAPI规范格式的JSON字符串

        Args:
            openapi_schema_srt: OpenAPI规范的JSON字符串

        Returns:
            OpenAPISchema: 解析后的OpenAPI模式对象

        Raises:
            ValidateErrorException: 当输入不是有效的JSON格式或不是字典类型时抛出

        """
        try:
            data = json.loads(openapi_schema_srt.strip())
            cls._validate_dict_format(data)
        except json.JSONDecodeError as e:
            error_msg = "数据必须符合 openapi 规范的 json 格式"
            raise ValidateErrorException(error_msg) from e

        return OpenAPISchema(**data)

    def create_api_tool_provider(self, req: CreateApiToolReq) -> None:
        """创建API工具提供者和相关的API工具

        Args:
            req (CreateApiToolReq): 创建API工具的请求对象，包含以下字段：
                - name: API工具提供者名称
                - icon: API工具提供者图标
                - openapi_schema: OpenAPI规范格式的schema字符串
                - headers: API请求所需的headers

        Raises:
            ValidateErrorException: 当已存在同名的API工具提供者时抛出

        Returns:
            None

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"
        # 解析OpenAPI schema字符串为结构化对象
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)
        # 查询是否已存在同名的API工具提供者
        api_tool_provider = (
            self.db.session.query(ApiToolProvider)
            .filter_by(
                account_id=account_id,
                name=req.name.data,
            )
            .one_or_none()
        )
        # 如果已存在，抛出验证错误异常
        if api_tool_provider:
            error_msg = f"API {req.name.data} 已存在"
            raise ValidateErrorException(error_msg)

        # 使用自动提交事务创建API工具提供者和相关API工具
        api_tool_provider = self.create(
            ApiToolProvider,
            account_id=account_id,
            name=req.name.data,
            icon=req.icon.data,
            openapi_schema=req.openapi_schema.data,
            description=openapi_schema.description,
            headers=req.headers.data,
        )

        # 遍历OpenAPI schema中的所有路径和方法
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                # 为每个API方法创建对应的API工具记录
                self.create(
                    ApiTool,
                    account_id=account_id,
                    provider_id=api_tool_provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    # 组合服务器基础URL和路径形成完整的API端点
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    def api_tool_invoke(self) -> None:
        provider_id = "6db32d9b-cf5c-4df8-9ecf-7a4e7339e53e"
        tool_name = "getWordSuggestions"

        api_tool = (
            self.db.session.query(ApiTool)
            .filter(
                ApiTool.provider_id == provider_id,
                ApiTool.name == tool_name,
            )
            .one_or_none()
        )

        api_tool_provider = api_tool.provider

        from src.core.tools.api_tool.entities import ToolEntity

        tool = self.api_provider_manager.get_tool(
            ToolEntity(
                id=provider_id,
                name=tool_name,
                url=api_tool.url,
                method=api_tool.method,
                parameters=api_tool.parameters,
                headers=api_tool_provider.headers,
                description=api_tool.description,
            ),
        )

        return tool.invoke({"q": "dog", "doctype": "json"})
