from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from flask import request
from injector import inject
from sqlalchemy import func

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from src.core.tools.builtin_tools.providers.builtin_provider_manager import (
    BuiltinProviderManager,
)
from src.entity.app_entity import (
    DEFAULT_APP_CONFIG,
    MAX_DATASET_COUNT,
    MAX_DIALOG_ROUNDS,
    MAX_OPENING_QUESTIONS_COUNT,
    MAX_OPENING_STATEMENT_LENGTH,
    MAX_PRESET_PROMPT_LENGTH,
    MAX_RETRIEVAL_COUNT,
    MAX_REVIEW_KEYWORDS_COUNT,
    MAX_TOOL_COUNT,
    AppConfigType,
    AppStatus,
)
from src.exception.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from src.lib.helper import datetime_to_timestamp
from src.model import App
from src.model.account import Account
from src.model.api_tool import ApiTool
from src.model.app import AppConfig, AppConfigVersion, AppDatasetJoin
from src.model.dataset import Dataset
from src.schemas.app_schema import (
    CreateAppReq,
    FallbackHistoryToDraftReq,
    GetPublishHistoriesWithPageReq,
)
from src.service.base_service import BaseService


@inject
@dataclass
class AppService(BaseService):
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager

    def fallback_history_to_draft(
        self,
        app_id: UUID,
        req: FallbackHistoryToDraftReq,
        account: Account,
    ) -> AppConfigVersion:
        """将历史版本回退到草稿配置

        Args:
            app_id (UUID): 应用ID，用于标识要操作的应用
            req (FallbackHistoryToDraftReq): 回退请求参数，包含要回退的版本ID
            account (Account): 当前操作用户的账户信息

        Returns:
            AppConfigVersion: 更新后的草稿配置版本对象

        Raises:
            NotFoundException: 当应用或配置版本不存在时抛出
            PermissionError: 当用户没有操作权限时抛出
            ValidationError: 当配置数据验证失败时抛出

        Note:
            - 会验证用户是否有权限访问该应用
            - 验证指定的历史版本是否存在
            - 复制历史版本的配置数据到草稿配置
            - 移除不需要的字段（如id、版本号、时间戳等）
            - 对配置数据进行验证
            - 更新草稿配置记录，并记录更新时间

        """
        app = self.get_app(app_id, account)

        app_config_version = self.get(AppConfigVersion, req.app_config_version_id.data)
        if not app_config_version:
            error_msg = "该应用配置版本不存在"
            raise NotFoundException(error_msg)

        # 复制草稿配置数据，准备创建版本记录
        draft_app_config_copy = app_config_version.__dict__.copy()
        # 定义需要移除的字段列表
        remove_fields = [
            "id",
            "app_id",
            "version",
            "config_type",
            "updated_at",
            "created_at",
            "_sa_instance_state",
        ]
        # 移除不需要的字段
        for field in remove_fields:
            draft_app_config_copy.pop(field, None)

        # 验证草稿配置数据
        draft_app_config_dict = self._validate_draft_app_config(
            draft_app_config_copy,
            account,
        )

        # 更新草稿配置记录
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            updated_at=datetime.now(UTC),
            **draft_app_config_dict,
        )

        return draft_app_config_dict

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """取消发布应用的草稿配置。

        将应用的状态设置为草稿状态，并删除应用配置记录。

        Args:
            app_id: 应用ID
            account: 账户信息

        """
        app = self.get_app(app_id, account)
        if app.status != AppStatus.PUBLISHED:
            error_msg = "应用未发布，无法取消发布"
            raise FailException(error_msg)

        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        return app

    def get_publish_histories_with_page(
        self,
        app_id: UUID,
        req: GetPublishHistoriesWithPageReq,
        account: Account,
    ) -> tuple[list[AppConfigVersion], Paginator]:
        """获取应用的发布历史记录（分页查询）

        Args:
            app_id (UUID): 应用ID，用于标识要查询的应用
            req (GetPublishHistoriesWithPageReq): 分页请求参数，包含页码、每页大小等信息
            account (Account): 当前操作用户的账户信息

        Returns:
            tuple[list[AppConfigVersion], Paginator]:
                - list[AppConfigVersion]: 应用配置版本列表，按版本号降序排列
                - Paginator: 分页器对象，包含分页相关信息

        Raises:
            NotFoundError: 当应用不存在时抛出
            PermissionError: 当用户没有访问该应用的权限时抛出

        Note:
            - 只返回已发布状态(PUBLISHED)的配置版本
            - 结果按版本号降序排列，最新版本在前
            - 使用分页器处理分页逻辑
            - 会验证用户是否有权限访问该应用

        """
        self.get_app(app_id, account)

        paginator = Paginator(db=self.db, req=req)

        app_config_versions = paginator.paginate(
            self.db.session.query(AppConfigVersion)
            .filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            )
            .order_by(AppConfigVersion.version.desc()),
        )

        return app_config_versions, paginator

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """发布应用的草稿配置。

        将应用的草稿配置发布为正式配置，包括：
        - 创建新的应用配置记录
        - 更新应用状态为已发布
        - 更新数据集关联
        - 创建配置版本记录

        Args:
            app_id: 应用ID
            account: 执行操作的账户信息

        Returns:
            App: 更新后的应用对象

        Raises:
            ForbiddenException: 当账户无权操作该应用时
            NotFoundException: 当应用不存在时
            ValidateErrorException: 当草稿配置验证失败时

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)
        # 获取应用的草稿配置
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 创建新的应用配置记录
        app_config = self.create(
            AppConfig,
            app_id=app_id,
            # 设置模型配置
            model_config=draft_app_config["model_config"],
            # 设置对话轮次配置
            dialog_round=draft_app_config["dialog_round"],
            # 设置预设提示词
            preset_prompt=draft_app_config["preset_prompt"],
            # 处理工具配置，转换为标准格式
            tools=[
                {
                    "type": tool["type"],
                    "provider_id": tool["provider"]["id"],
                    "tool_id": tool["tool"]["name"],
                    "params": tool["tool"]["params"],
                }
                for tool in draft_app_config["tools"]
            ],
            # 设置工作流配置
            workflows=draft_app_config["workflows"],
            # 设置检索配置
            retrieval_config=draft_app_config["retrieval_config"],
            # 设置长期记忆配置
            long_term_memory=draft_app_config["long_term_memory"],
            # 设置开场白
            opening_statement=draft_app_config["opening_statement"],
            # 设置开场问题
            opening_questions=draft_app_config["opening_questions"],
            # 设置语音转文字配置
            speech_to_text=draft_app_config["speech_to_text"],
            # 设置文字转语音配置
            text_to_speech=draft_app_config["text_to_speech"],
            # 设置审核配置
            review_config=draft_app_config["review_config"],
        )

        # 更新应用状态为已发布，并关联新的配置ID
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 使用事务上下文，删除原有的数据集关联
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 创建新的数据集关联记录
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 复制草稿配置数据，准备创建版本记录
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        # 定义需要移除的字段列表
        remove_fields = [
            "id",
            "version",
            "config_type",
            "updated_at",
            "created_at",
            "_sa_instance_state",
        ]
        # 移除不需要的字段
        for field in remove_fields:
            draft_app_config_copy.pop(field, None)

        # 查询当前最大的已发布版本号
        max_version = (
            self.db.session.query(
                func.coalesce(func.max(AppConfigVersion.version), 1),
            )
            .filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            )
            .scalar()
        )

        # 创建新的配置版本记录
        self.create(
            AppConfigVersion,
            # 版本号递增
            version=max_version + 1,
            # 设置配置类型为已发布
            config_type=AppConfigType.PUBLISHED,
            # 复制草稿配置的其他字段
            **draft_app_config_copy,
        )

        # 返回更新后的应用对象
        return app

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

        该方法会获取指定应用的草稿配置，并对配置中的工具、知识库等信息进行验证和格式化。
        主要包括：
        1. 验证内置工具和API工具的配置
        2. 验证知识库的存在性
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
                - datasets: 知识库配置列表
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

        # 处理知识库配置
        datasets = []
        # 获取草稿配置中的知识库ID列表
        draft_datasets = draft_app_config.datasets
        # 查询所有相关的知识库记录
        dataset_records = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(draft_datasets),
            )
            .all()
        )
        # 构建知识库ID到记录的映射
        dataset_dict = {
            str(dataset_record.id): dataset_record for dataset_record in dataset_records
        }
        dataset_sets = set(dataset_dict.keys())

        # 筛选出存在的知识库ID
        exist_dataset_ids = [
            dataset_id for dataset_id in draft_datasets if dataset_id in dataset_sets
        ]

        # 如果知识库配置有变化，更新数据库
        if set(exist_dataset_ids) != set(draft_datasets):
            self.update(draft_app_config, datasets=exist_dataset_ids)

        # 构建返回的知识库信息
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

    def update_draft_app_config(
        self,
        app_id: UUID,
        draft_app_config: dict[str, Any],
        account: Account,
    ) -> dict[str, Any]:
        """更新应用的草稿配置。

        Args:
            app_id: 应用ID
            draft_app_config: 待更新的草稿配置字典
            account: 执行更新的账户对象

        Returns:
            dict[str, Any]: 更新后的草稿配置记录

        """
        # 获取应用信息，验证应用存在性和所有权
        app = self.get_app(app_id, account)

        # 验证草稿配置的合法性和完整性
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 获取应用的当前草稿配置记录
        draft_app_config_record = app.draft_app_config
        # 更新草稿配置，包括更新时间和配置内容
        self.update(
            draft_app_config_record,
            updated_at=datetime.now(UTC),
            **draft_app_config,
        )

        # 返回更新后的草稿配置记录
        return draft_app_config_record

    def _validate_model_config(self, model_config: dict) -> dict:
        """验证模型配置

        Args:
            model_config: 模型配置字典

        Returns:
            dict: 验证后的模型配置

        Raises:
            ValidateErrorException: 当模型配置格式错误时抛出

        """
        # TODO: 实现模型配置验证逻辑
        return model_config

    def _validate_dialog_round(self, dialog_round: dict) -> dict:
        """验证对话轮数配置

        Args:
            dialog_round: 对话轮数配置

        Returns:
            dict: 验证后的对话轮数配置

        Raises:
            ValidateErrorException: 当对话轮数配置错误时抛出

        """
        if not isinstance(dialog_round, int) or not (
            0 <= dialog_round <= MAX_DIALOG_ROUNDS
        ):
            error_msg = f"对话轮数配置必须整数，应为0~{MAX_DIALOG_ROUNDS}之间的整数"
            raise ValidateErrorException(error_msg)
        return dialog_round

    def _validate_preset_prompt(self, preset_prompt: str) -> str:
        """验证预设提示词配置

        Args:
            preset_prompt: 预设提示词

        Returns:
            str: 验证后的预设提示词

        Raises:
            ValidateErrorException: 当预设提示词配置错误时抛出

        """
        if (
            not isinstance(preset_prompt, str)
            or len(preset_prompt) > MAX_PRESET_PROMPT_LENGTH
        ):
            error_msg = f"预设提示词配置格式错误, 长度应小于{MAX_PRESET_PROMPT_LENGTH}"
            raise ValidateErrorException(error_msg)
        return preset_prompt

    def _validate_tools(self, tools: list, account: Account) -> list:  # noqa: PLR0912
        """验证工具配置

        Args:
            tools: 工具配置列表
            account: 用户账户信息

        Returns:
            list: 验证后的工具配置列表

        Raises:
            ValidateErrorException: 当工具配置错误时抛出

        """
        validate_tools = []
        if not isinstance(tools, list):
            error_msg = "工具配置格式错误，应为列表"
            raise ValidateErrorException(error_msg)
        if len(tools) > MAX_TOOL_COUNT:
            error_msg = f"工具数量超过最大限制{MAX_TOOL_COUNT}"
            raise ValidateErrorException(error_msg)
        for tool in tools:
            if not tool or not isinstance(tool, dict):
                error_msg = "工具配置格式错误，应为字典"
                raise ValidateErrorException(error_msg)
            if set(tool.keys()) != {"tool_id", "type", "provider_id", "params"}:
                error_msg = "工具配置格式错误，字段不匹配"
                raise ValidateErrorException(error_msg)
            if tool["type"] not in ["builtin_tool", "api_tool"]:
                error_msg = "工具类型错误，应为builtin_tool或api_tool"
                raise ValidateErrorException(error_msg)
            if (
                not tool["provider_id"]
                or not tool["tool_id"]
                or not isinstance(tool["provider_id"], str)
                or not isinstance(tool["tool_id"], str)
            ):
                error_msg = "工具配置格式错误，provider_id或tool_id应为字符串"
                raise ValidateErrorException(error_msg)
            if not isinstance(tool["params"], dict):
                error_msg = "工具配置格式错误，params应为字典"
                raise ValidateErrorException(error_msg)
            if tool["type"] == "builtin_tool":
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider_id"],
                    tool["tool_id"],
                )
                if not builtin_tool:
                    continue
            else:
                api_tool = (
                    self.db.session.query(ApiTool)
                    .filter(
                        ApiTool.provider_id == tool["provider_id"],
                        ApiTool.name == tool["tool_id"],
                        ApiTool.account_id == account.id,
                    )
                    .one_or_none()
                )
                if not api_tool:
                    continue
            validate_tools.append(tool)

        check_tools = [
            f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools
        ]
        if len(set(check_tools)) != len(validate_tools):
            error_msg = "工具列表中存在重复的工具"
            raise ValidateErrorException(error_msg)
        return validate_tools

    def _validate_workflows(self, workflows: list) -> list:
        """验证工作流配置

        Args:
            workflows: 工作流配置列表

        Returns:
            list: 验证后的工作流配置列表

        Raises:
            ValidateErrorException: 当工作流配置错误时抛出

        """
        # TODO: 实现工作流验证逻辑
        return []

    def _validate_datasets(self, datasets: list, account: Account) -> list:
        """验证知识库配置

        Args:
            datasets: 知识库ID列表
            account: 用户账户信息

        Returns:
            list: 验证后的知识库ID列表

        Raises:
            ValidateErrorException: 当知识库配置错误时抛出

        """
        if not isinstance(datasets, list):
            error_msg = "知识库列表必须是列表类型"
            raise ValidateErrorException(error_msg)
        if len(datasets) > MAX_DATASET_COUNT:
            error_msg = f"知识库数量不能超过{MAX_DATASET_COUNT}"
            raise ValidateErrorException(error_msg)
        for dataset_id in datasets:
            try:
                UUID(dataset_id)
            except Exception as e:
                error_msg = "知识库ID必须是UUID类型"
                raise ValidateErrorException(error_msg) from e
        if len(set(datasets)) != len(datasets):
            error_msg = "知识库列表中存在重复的知识库"
            raise ValidateErrorException(error_msg)
        dataset_records = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            )
            .all()
        )
        dataset_sets = {str(dataset_record.id) for dataset_record in dataset_records}
        return [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

    def _validate_retrieval_config(self, retrieval_config: dict) -> dict:
        """验证检索配置

        Args:
            retrieval_config: 检索配置字典

        Returns:
            dict: 验证后的检索配置

        Raises:
            ValidateErrorException: 当检索配置错误时抛出

        """
        if not retrieval_config or not isinstance(retrieval_config, dict):
            error_msg = "检索配置必须是字典类型"
            raise ValidateErrorException(error_msg)
        if set(retrieval_config.keys()) != {
            "retrieval_strategy",
            "k",
            "score",
        }:
            error_msg = "检索配置必须包含检索策略、检索数量和检索分数"
            raise ValidateErrorException(error_msg)
        if retrieval_config["retrieval_strategy"] not in [
            "semantic",
            "full_text",
            "hybrid",
        ]:
            error_msg = "检索策略必须是语义检索、全文检索或混合检索"
            raise ValidateErrorException(error_msg)
        if not isinstance(retrieval_config["k"], int) or not (
            0 <= retrieval_config["k"] <= MAX_RETRIEVAL_COUNT
        ):
            error_msg = f"检索数量必须是整数，且在0到{MAX_RETRIEVAL_COUNT}之间"
            raise ValidateErrorException(error_msg)
        if not isinstance(retrieval_config["score"], float) or not (
            0 <= retrieval_config["score"] <= 1
        ):
            error_msg = "检索分数必须是浮点数，且在0到1之间"
            raise ValidateErrorException(error_msg)
        return retrieval_config

    def _validate_long_term_memory(self, long_term_memory: dict) -> dict:
        """验证长期记忆配置

        Args:
            long_term_memory: 长期记忆配置字典

        Returns:
            dict: 验证后的长期记忆配置

        Raises:
            ValidateErrorException: 当长期记忆配置错误时抛出

        """
        if not long_term_memory or not isinstance(long_term_memory, dict):
            error_msg = "长期记忆配置必须是字典"
            raise ValidateErrorException(error_msg)
        if set(long_term_memory.keys()) != {"enable"} or not isinstance(
            long_term_memory["enable"],
            bool,
        ):
            error_msg = (
                "长期记忆配置必须是包含enable键的字典，且enable的值必须是布尔类型"
            )
            raise ValidateErrorException(error_msg)
        return long_term_memory

    def _validate_opening_statement(self, opening_statement: str) -> str:
        """验证开场白配置

        Args:
            opening_statement: 开场白文本

        Returns:
            str: 验证后的开场白文本

        Raises:
            ValidateErrorException: 当开场白配置错误时抛出

        """
        if (
            not isinstance(opening_statement, str)
            or len(opening_statement) > MAX_OPENING_STATEMENT_LENGTH
        ):
            error_msg = (
                f"开场白必须是字符串，且长度不能超过{MAX_OPENING_STATEMENT_LENGTH}"
            )
            raise ValidateErrorException(error_msg)
        return opening_statement

    def _validate_opening_questions(self, opening_questions: list) -> list:
        """验证开场问题配置

        Args:
            opening_questions: 开场问题列表

        Returns:
            list: 验证后的开场问题列表

        Raises:
            ValidateErrorException: 当开场问题配置错误时抛出

        """
        if (
            not isinstance(opening_questions, list)
            or len(opening_questions) > MAX_OPENING_QUESTIONS_COUNT
        ):
            error_msg = (
                f"开场白问题必须是列表，且个数不能超过{MAX_OPENING_QUESTIONS_COUNT}"
            )
            raise ValidateErrorException(error_msg)
        for question in opening_questions:
            if not isinstance(question, str):
                error_msg = "开场白问题必须是字符串"
                raise ValidateErrorException(error_msg)
        return opening_questions

    def _validate_speech_to_text(self, speech_to_text: dict) -> dict:
        """验证语音转文本配置

        Args:
            speech_to_text: 语音转文本配置字典

        Returns:
            dict: 验证后的语音转文本配置

        Raises:
            ValidateErrorException: 当语音转文本配置错误时抛出

        """
        if not speech_to_text or not isinstance(speech_to_text, dict):
            error_msg = "语音转文本配置必须是字典"
            raise ValidateErrorException(error_msg)
        if set(speech_to_text.keys()) != {"enable"} or not isinstance(
            speech_to_text["enable"],
            bool,
        ):
            error_msg = (
                "语音转文本配置必须是包含enable键的字典，且enable的值必须是布尔类型"
            )
            raise ValidateErrorException(error_msg)
        return speech_to_text

    def _validate_text_to_speech(self, text_to_speech: dict) -> dict:
        """验证文本转语音配置

        Args:
            text_to_speech: 文本转语音配置字典

        Returns:
            dict: 验证后的文本转语音配置

        Raises:
            ValidateErrorException: 当文本转语音配置错误时抛出

        """
        if not text_to_speech or not isinstance(text_to_speech, dict):
            error_msg = "文本转语音配置必须是字典"
            raise ValidateErrorException(error_msg)
        if (
            set(text_to_speech.keys())
            != {
                "enable",
                "voice",
                "auto_play",
            }
            or not isinstance(text_to_speech["enable"], bool)
            # TODO: voice类型需要进一步确认
            or not isinstance(
                text_to_speech["voice"],
                str,
            )
            or not isinstance(text_to_speech["auto_play"], bool)
        ):
            error_msg = (
                "文本转语音配置必须是包含enable、voice、auto_play键的字典，且enable的值必须是布尔类型，"
                "voice的值必须是字符串，auto_play的值必须是布尔类型"
            )
            raise ValidateErrorException(error_msg)
        return text_to_speech

    def _validate_review_config(self, review_config: dict) -> dict:
        """验证审核配置

        Args:
            review_config: 审核配置字典

        Returns:
            dict: 验证后的审核配置

        Raises:
            ValidateErrorException: 当审核配置错误时抛出

        """
        if not review_config or not isinstance(review_config, dict):
            error_msg = "审核配置必须是字典"
            raise ValidateErrorException(error_msg)
        if set(review_config.keys()) != {
            "enable",
            "keywords",
            "inputs_config",
            "outputs_config",
        }:
            error_msg = (
                "审核配置必须是包含enable、keywords、inputs_config、"
                "outputs_config键的字典"
            )
            raise ValidateErrorException(error_msg)
        if (
            not isinstance(review_config["keywords"], list)
            or (review_config["enable"] and len(review_config["keywords"]) == 0)
            or len(review_config["keywords"]) > MAX_REVIEW_KEYWORDS_COUNT
        ):
            error_msg = f"keywords必须是长度为1-{MAX_REVIEW_KEYWORDS_COUNT}的列表"
            raise ValidateErrorException(error_msg)
        for keyword in review_config["keywords"]:
            if not isinstance(keyword, str):
                error_msg = "keywords必须是字符串"
                raise ValidateErrorException(error_msg)
        if not review_config["inputs_config"] or not isinstance(
            review_config["inputs_config"],
            dict,
        ):
            error_msg = "inputs_config必须是字典"
            raise ValidateErrorException(error_msg)
        if (
            set(review_config["inputs_config"].keys())
            != {
                "enable",
                "preset_response",
            }
            or not isinstance(review_config["inputs_config"]["enable"], bool)
            or not isinstance(
                review_config["inputs_config"]["preset_response"],
                str,
            )
        ):
            error_msg = (
                "inputs_config必须是包含enable、preset_response键的字典, "
                "enable必须是布尔值，preset_response必须是字符串"
            )
            raise ValidateErrorException(error_msg)
        if not review_config["outputs_config"] or not isinstance(
            review_config["outputs_config"],
            dict,
        ):
            error_msg = "outputs_config必须是字典"
            raise ValidateErrorException(error_msg)
        if set(review_config["outputs_config"].keys()) != {
            "enable",
        } or not isinstance(review_config["outputs_config"]["enable"], bool):
            error_msg = "outputs_config必须是包含enable键的字典, 且enable必须是布尔值"
            raise ValidateErrorException(error_msg)
        if (
            review_config["enable"]
            and review_config["inputs_config"]["enable"] is False
            and review_config["outputs_config"]["enable"] is False
        ):
            error_msg = "enable为True时，inputs_config和outputs_config至少有一个为True"
            raise ValidateErrorException(error_msg)
        if (
            review_config["enable"]
            and review_config["inputs_config"]["enable"]
            and review_config["inputs_config"]["preset_response"].strip() == ""
        ):
            error_msg = "preset_response不能为空"
            raise ValidateErrorException(error_msg)
        return review_config

    def _validate_draft_app_config(  # noqa: PLR0912
        self,
        draft_app_config: dict[str, Any],
        account: Account,
    ) -> dict:
        """验证草稿应用配置

        Args:
            draft_app_config: 草稿应用配置字典
            account: 用户账户信息

        Returns:
            dict: 验证后的草稿应用配置

        Raises:
            ValidateErrorException: 当草稿配置格式错误时抛出

        """
        # 定义允许的配置字段列表
        acceptable_fields = [
            "model_config",  # 模型配置
            "dialog_round",  # 对话轮次配置
            "preset_prompt",  # 预设提示词
            "tools",  # 工具配置
            "workflows",  # 工作流配置
            "datasets",  # 知识库配置
            "retrieval_config",  # 检索配置
            "long_term_memory",  # 长期记忆配置
            "opening_statement",  # 开场白
            "opening_questions",  # 开场问题
            "speech_to_text",  # 语音转文字配置
            "text_to_speech",  # 文字转语音配置
            "review_config",  # 审核配置
        ]

        # 验证配置格式：
        # 1. 配置不能为空
        # 2. 配置必须是字典类型
        # 3. 配置中的所有字段都必须在允许的字段列表中
        if (
            not draft_app_config
            or not isinstance(draft_app_config, dict)
            or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            error_msg = "草稿配置格式错误"
            raise ValidateErrorException(error_msg)

        # 验证模型配置
        if "model_config" in draft_app_config:
            draft_app_config["model_config"] = self._validate_model_config(
                draft_app_config["model_config"],
            )

        # 验证对话轮次配置
        if "dialog_round" in draft_app_config:
            draft_app_config["dialog_round"] = self._validate_dialog_round(
                draft_app_config["dialog_round"],
            )

        # 验证预设提示词
        if "preset_prompt" in draft_app_config:
            draft_app_config["preset_prompt"] = self._validate_preset_prompt(
                draft_app_config["preset_prompt"],
            )

        # 验证工具配置
        if "tools" in draft_app_config:
            draft_app_config["tools"] = self._validate_tools(
                draft_app_config["tools"],
                account,
            )

        # 验证工作流配置
        if "workflows" in draft_app_config:
            draft_app_config["workflows"] = self._validate_workflows(
                draft_app_config["workflows"],
            )

        # 验证知识库配置
        if "datasets" in draft_app_config:
            draft_app_config["datasets"] = self._validate_datasets(
                draft_app_config["datasets"],
                account,
            )

        # 验证检索配置
        if "retrieval_config" in draft_app_config:
            draft_app_config["retrieval_config"] = self._validate_retrieval_config(
                draft_app_config["retrieval_config"],
            )

        # 验证长期记忆配置
        if "long_term_memory" in draft_app_config:
            draft_app_config["long_term_memory"] = self._validate_long_term_memory(
                draft_app_config["long_term_memory"],
            )

        # 验证开场白
        if "opening_statement" in draft_app_config:
            draft_app_config["opening_statement"] = self._validate_opening_statement(
                draft_app_config["opening_statement"],
            )

        # 验证开场问题
        if "opening_questions" in draft_app_config:
            draft_app_config["opening_questions"] = self._validate_opening_questions(
                draft_app_config["opening_questions"],
            )

        # 验证语音转文字配置
        if "speech_to_text" in draft_app_config:
            draft_app_config["speech_to_text"] = self._validate_speech_to_text(
                draft_app_config["speech_to_text"],
            )

        # 验证文字转语音配置
        if "text_to_speech" in draft_app_config:
            draft_app_config["text_to_speech"] = self._validate_text_to_speech(
                draft_app_config["text_to_speech"],
            )

        # 验证审核配置
        if "review_config" in draft_app_config:
            draft_app_config["review_config"] = self._validate_review_config(
                draft_app_config["review_config"],
            )

        # 返回验证后的配置
        return draft_app_config
