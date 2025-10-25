import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from injector import inject

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.tools.api_tool.entities.openapi_schema import OpenAPISchema
from src.exception.exception import ValidateErrorException
from src.model.api_tool import ApiTool
from src.model.api_tool_provider import ApiToolProvider
from src.schemas.api_tool_schema import CreateApiToolReq


@inject
@dataclass
class ApiToolService:
    """API工具服务类，用于处理OpenAPI规范相关的操作"""

    db: SQLAlchemy

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
        account_id = (
            "9495d2e2-2e7a-4484-8447-03f6b24627f7"  # 临时硬编码的账户ID，用于权限验证
        )

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
            raise ValidateErrorException(error_msg)  # 抛出验证错误异常

        return api_tool  # 返回查询到的API工具对象

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
        api_tool_provider = self.db.session.query(ApiToolProvider).get(provider_id)
        # 验证API工具提供者是否存在且属于当前账户
        if api_tool_provider is None or str(api_tool_provider.account_id) != account_id:
            # 构造错误信息
            error_msg = f"API工具提供者不存在: {provider_id}"
            # 抛出验证错误异常
            raise ValidateErrorException(error_msg)

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

    def create_api_tool(self, req: CreateApiToolReq) -> None:
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
        with self.db.auto_commit():
            # 创建API工具提供者记录
            api_tool_provider = ApiToolProvider(
                account_id=account_id,
                name=req.name.data,
                icon=req.icon.data,
                openapi_schema=req.openapi_schema.data,
                description=openapi_schema.description,
                headers=req.headers.data,
            )
            # 将API工具提供者添加到会话中
            self.db.session.add(api_tool_provider)
            # 刷新会话以获取新创建的提供者ID
            self.db.session.flush()

            # 遍历OpenAPI schema中的所有路径和方法
            for path, path_item in openapi_schema.paths.items():
                for method, method_item in path_item.items():
                    # 为每个API方法创建对应的API工具记录
                    api_tool = ApiTool(
                        account_id=account_id,
                        provider_id=api_tool_provider.id,
                        name=method_item.get("operationId"),
                        description=method_item.get("description"),
                        # 组合服务器基础URL和路径形成完整的API端点
                        url=f"{openapi_schema.server}{path}",
                        method=method,
                        parameters=method_item.get("parameters", []),
                    )
                    # 将API工具添加到会话中
                    self.db.session.add(api_tool)
