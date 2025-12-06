from dataclasses import dataclass
from uuid import UUID

from flask import request
from injector import inject

from pkg.sqlalchemy import SQLAlchemy
from src.core.tools.builtin_tools.providers.builtin_provider_manager import (
    BuiltinProviderManager,
)
from src.entity.app_entity import DEFAULT_APP_CONFIG, AppConfigType, AppStatus
from src.exception.exception import ForbiddenException, NotFoundException
from src.lib.helper import datetime_to_timestamp
from src.model import App
from src.model.account import Account
from src.model.api_tool import ApiTool
from src.model.app import AppConfigVersion
from src.model.dataset import Dataset
from src.schemas.app_schema import CreateAppReq
from src.service.base_service import BaseService


@inject
@dataclass
class AppService(BaseService):
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """创建新应用

        Args:
            req: 创建应用的请求参数，包含应用名称、图标、描述等信息
            account: 创建应用的用户账号信息

        Returns:
            App: 创建成功的应用对象

        """
        # 使用数据库事务上下文，确保操作的原子性
        with self.db.auto_commit():
            # 创建应用实体对象
            app = App(
                account_id=account.id,  # 关联用户ID
                name=req.name.data,  # 应用名称
                icon=req.icon.data,  # 应用图标
                description=req.description.data,  # 应用描述
                status=AppStatus.DRAFT,  # 初始状态为草稿
            )
            # 将应用对象添加到数据库会话中
            self.db.session.add(app)
            # 刷新会话，获取应用ID
            self.db.session.flush()

            # 创建应用配置版本对象
            app_config_version = AppConfigVersion(
                app_id=app.id,  # 关联应用ID
                version=1,  # 初始版本号
                config_type=AppConfigType.DRAFT,  # 配置类型为草稿
                **DEFAULT_APP_CONFIG,  # 使用默认配置
            )
            # 将配置版本对象添加到数据库会话中
            self.db.session.add(app_config_version)
            # 刷新会话，获取配置版本ID
            self.db.session.flush()

            # 将草稿配置ID关联到应用对象
            app.draft_app_config_id = app_config_version.id

        # 返回创建的应用对象
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """获取应用信息

        Args:
            app_id: 应用ID，用于唯一标识一个应用
            account: 用户账号信息，用于验证应用所有权

        Returns:
            App: 返回获取到的应用对象

        Raises:
            NotFoundException: 当应用不存在时抛出
            ForbiddenException: 当应用不属于当前用户时抛出

        """
        # 根据应用ID查询应用信息
        app = self.get(App, app_id)
        # 检查应用是否存在
        if not app:
            error_msg = f"应用 {app_id} 不存在"
            raise NotFoundException(error_msg)

        # 验证应用所有权，确保只有应用所有者才能访问
        if app.account_id != account.id:
            error_msg = f"应用 {app_id} 不属于当前用户"
            raise ForbiddenException(error_msg)

        # 返回应用对象
        return app

    def update_app(self, app_id: UUID) -> App:
        with self.db.auto_commit():
            app: App = self.get_app(app_id)
            app.name = "聊天机器人6"

        return app

    def delete_app(self, app_id: UUID) -> App:
        with self.db.auto_commit():
            app: App = self.get_app(app_id)
            self.db.session.delete(app)

        return app

    def get_draft_app_config(self, app_id: UUID, account: Account) -> dict:
        """获取应用的草稿配置信息。

        该方法会获取指定应用的草稿配置，并对配置中的工具、数据集等信息进行验证和格式化。
        主要包括：
        1. 验证内置工具和API工具的配置
        2. 验证数据集的存在性
        3. 格式化返回的配置信息

        Args:
            app_id (UUID): 应用的唯一标识符
            account (Account): 当前操作的用户账户信息

        Returns:
            dict: 包含完整草稿配置信息的字典，包括：
                - id: 配置ID
                - model_config: 模型配置
                - dialog_round: 对话轮次
                - preset_prompt: 预设提示词
                - tools: 工具配置列表
                - workflows: 工作流配置列表
                - datasets: 数据集配置列表
                - retrieval_config: 检索配置
                - long_term_memory: 长期记忆配置
                - opening_statement: 开场白
                - opening_questions: 开场问题列表
                - speech_to_text: 语音转文本配置
                - text_to_speech: 文本转语音配置
                - review_config: 审核配置
                - created_at: 创建时间戳
                - updated_at: 更新时间戳

        """
        # 获取应用信息
        app = self.get_app(app_id, account)

        # 获取应用的草稿配置
        draft_app_config = app.draft_app_config

        # TODO: 校验 model_config 配置

        # 获取草稿配置中的工具列表
        draft_tools = draft_app_config.tools
        # 初始化验证后的工具列表和返回的工具列表
        validate_tools = []
        tools = []

        # 遍历处理每个工具
        for draft_tool in draft_tools:
            # 处理内置工具
            if draft_tool["type"] == "builtin_tool":
                # 获取工具提供者
                provider_entity = self.builtin_provider_manager.get_provider(
                    draft_tool["provider_id"],
                )
                if not provider_entity:
                    continue

                # 获取工具实体
                tool_entity = provider_entity.get_tool_entity(draft_tool["tool_id"])
                if not tool_entity:
                    continue

                # 验证工具参数
                param_keys = {param.name for param in tool_entity.params}
                params = draft_tool["params"]
                # 如果参数不匹配，使用默认参数
                if set(draft_tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }

                # 添加验证后的工具配置
                validate_tools.append({**draft_tool, "params": params})
                # 构建返回的工具信息
                tools.append(
                    {
                        "type": "builtin_tool",
                        "provider": {
                            "id": provider_entity.name,
                            "name": provider_entity.name,
                            "label": provider_entity.name,
                            "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                        },
                        "tool": {
                            "id": tool_entity.name,
                            "name": tool_entity.name,
                            "label": tool_entity.name,
                            "description": tool_entity.description,
                            "params": draft_tool["params"],
                        },
                    },
                )
            # 处理API工具
            elif draft_tool["type"] == "api_tool":
                # 查询API工具记录
                tool_record = (
                    self.db.session.query(ApiTool)
                    .filter(
                        ApiTool.provider_id == draft_tool["provider_id"],
                        ApiTool.name == draft_tool["tool_id"],
                    )
                    .one_or_none()
                )
                if not tool_record:
                    continue

                # 添加验证后的工具配置
                validate_tools.append(draft_tool)
                # 获取工具提供者信息
                provider = tool_record.provider
                # 构建返回的工具信息
                tools.append(
                    {
                        "type": "api_tool",
                        "provider": {
                            "id": str(provider.id),
                            "name": provider.name,
                            "label": provider.name,
                            "icon": provider.icon,
                        },
                        "tool": {
                            "id": tool_record.name,
                            "name": tool_record.name,
                            "label": tool_record.name,
                            "description": tool_record.description,
                            "params": {},
                        },
                    },
                )

        # 如果工具配置有变化，更新数据库
        if draft_tools != validate_tools:
            self.update(draft_app_config, tools=validate_tools)

        # 处理数据集配置
        datasets = []
        # 获取草稿配置中的数据集ID列表
        draft_datasets = draft_app_config.datasets
        # 查询所有相关的数据集记录
        dataset_records = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(draft_datasets),
            )
            .all()
        )
        # 构建数据集ID到记录的映射
        dataset_dict = {
            str(dataset_record.id): dataset_record for dataset_record in dataset_records
        }
        dataset_sets = set(dataset_dict.keys())

        # 筛选出存在的数据集ID
        exist_dataset_ids = [
            dataset_id for dataset_id in draft_datasets if dataset_id in dataset_sets
        ]

        # 如果数据集配置有变化，更新数据库
        if set(exist_dataset_ids) != set(draft_datasets):
            self.update(draft_app_config, datasets=exist_dataset_ids)

        # 构建返回的数据集信息
        for dataset_id in exist_dataset_ids:
            dataset_record = dataset_dict.get(str(dataset_id))
            datasets.append(
                {
                    "id": str(dataset_id),
                    "name": dataset_record.name,
                    "icon": dataset_record.icon,
                    "description": dataset_record.description,
                },
            )

        # TODO: 校验工作流数据
        workflows = []

        # 返回完整的草稿配置信息
        return {
            "id": str(draft_app_config.id),
            "model_config": draft_app_config.model_config,
            "dialog_round": draft_app_config.dialog_round,
            "preset_prompt": draft_app_config.preset_prompt,
            "tools": tools,
            "workflows": workflows,
            "datasets": datasets,
            "retrieval_config": draft_app_config.retrieval_config,
            "long_term_memory": draft_app_config.long_term_memory,
            "opening_statement": draft_app_config.opening_statement,
            "opening_questions": draft_app_config.opening_questions,
            "speech_to_text": draft_app_config.speech_to_text,
            "text_to_speech": draft_app_config.text_to_speech,
            "review_config": draft_app_config.review_config,
            "created_at": datetime_to_timestamp(draft_app_config.created_at),
            "updated_at": datetime_to_timestamp(draft_app_config.updated_at),
        }
