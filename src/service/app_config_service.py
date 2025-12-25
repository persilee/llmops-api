from dataclasses import dataclass
from typing import Any

from flask import request
from injector import inject
from langchain.tools import BaseTool

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.tools.api_tool.entities.tool_entity import ToolEntity
from src.core.tools.builtin_tools.providers.builtin_provider_manager import (
    BuiltinProviderManager,
)
from src.core.tools.providers.api_provider_manager import ApiProviderManager
from src.lib.helper import datetime_to_timestamp
from src.model.api_tool import ApiTool
from src.model.app import App, AppConfig, AppConfigVersion, AppDatasetJoin
from src.model.dataset import Dataset
from src.service.base_service import BaseService


@inject
@dataclass
class AppConfigService(BaseService):
    """应用配置服务类。

    负责处理应用配置相关的所有业务逻辑，包括：
    - 获取和管理应用的草稿配置
    - 获取和管理应用的正式配置
    - 处理和验证工具配置
    - 处理和验证知识库配置
    - 处理工作流数据
    - 提供配置转换和验证的辅助方法

    Attributes:
        db: SQLAlchemy数据库实例，用于数据库操作
        builtin_provider_manager: 内置工具提供者管理器，用于管理内置工具
        api_provider_manager: API工具提供者管理器，用于管理API工具

    """

    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    api_provider_manager: ApiProviderManager

    def get_draft_app_config(self, app: App) -> dict[str, Any]:
        """获取应用的草稿配置信息。

        该方法会处理应用的草稿配置，包括：
        - 验证和处理工具配置
        - 验证和处理知识库配置
        - 初始化工作流列表
        - 返回整合后的完整配置信息

        Args:
            app (App): 应用实例对象，包含草稿配置信息

        Returns:
            dict[str, Any]: 包含以下内容的字典：
                - tools: 处理后的工具配置列表，用于前端展示
                - workflows: 工作流配置列表
                - datasets: 处理后的知识库配置列表，用于前端展示
                - 其他原始配置信息

        Note:
            如果工具或知识库配置发生变化，会自动更新数据库中的配置。

        """
        # 获取应用的草稿配置
        draft_app_config = app.draft_app_config

        # TODO: 校验 model_config 配置

        # 处理并验证工具配置
        # 返回两个列表：tools用于前端展示，validate_tools用于存储验证后的配置
        tools, validate_tools = self._process_and_validate_tools(draft_app_config.tools)

        # 如果工具配置发生变化，更新数据库中的配置
        if draft_app_config.tools != validate_tools:
            self.update(draft_app_config, tools=validate_tools)

        # 处理并验证知识库配置
        # 返回两个列表：datasets用于前端展示，validate_datasets用于存储验证后的配置
        datasets, validate_datasets = self._process_and_validate_datasets(
            draft_app_config.datasets,
        )

        # 如果知识库配置发生变化，更新数据库中的配置
        if set(validate_datasets) != set(draft_app_config.datasets):
            self.update(draft_app_config, datasets=validate_datasets)

        # TODO: 校验工作流数据
        workflows = []  # 初始化工作流列表

        # 返回完整的草稿配置信息
        # 将处理后的工具、工作流、知识库和原始配置整合并返回
        return self._process_and_transformer_app_config(
            tools,
            workflows,
            datasets,
            draft_app_config,
        )

    def get_app_config(self, app: App) -> dict[str, Any]:
        """获取应用的完整配置信息。

        该方法会处理并验证应用的工具配置、知识库配置和工作流配置，并将它们整合后返回。
        具体包括：
        1. 获取并验证工具配置，如果配置发生变化则更新数据库
        2. 获取并验证知识库配置，清理无效的知识库关联
        3. 处理工作流配置
        4. 将所有配置整合并返回

        Args:
            app (App): 应用对象，包含应用的基本信息和配置

        Returns:
            dict[str, Any]: 包含完整应用配置的字典，包括：
                - tools: 处理后的工具配置列表
                - workflows: 工作流配置列表
                - datasets: 处理后的知识库配置列表
                - 其他原始配置信息

        """
        # 获取应用的配置信息
        app_config = app.app_config

        # TODO: 校验 model_config 配置

        # 处理并验证工具配置
        # 返回两个列表：tools用于前端展示，validate_tools用于存储验证后的配置
        tools, validate_tools = self._process_and_validate_tools(app_config.tools)

        # 如果工具配置发生变化，更新数据库中的配置
        if app_config.tools != validate_tools:
            self.update(app_config, tools=validate_tools)

        # 获取应用关联的知识库配置
        app_dataset_joins = app_config.app_dataset_joins
        # 提取所有关联的知识库ID
        origin_datasets = [
            str(app_dataset_join.dataset_id) for app_dataset_join in app_dataset_joins
        ]
        # 处理并验证知识库配置
        # 返回两个列表：datasets用于前端展示，validate_datasets用于存储验证后的配置
        datasets, validate_datasets = self._process_and_validate_datasets(
            origin_datasets,
        )

        # 清理无效的知识库关联
        # 找出原始知识库中但未通过验证的知识库ID
        for dataset_id in set(origin_datasets) - set(validate_datasets):
            # 在自动提交的事务中删除无效的知识库关联记录
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(
                    AppDatasetJoin.dataset_id == dataset_id,
                ).delete()

        # TODO: 校验工作流数据
        workflows = []

        # 返回完整的配置信息
        # 将处理后的工具、工作流、知识库和原始配置整合并返回
        return self._process_and_transformer_app_config(
            tools,
            workflows,
            datasets,
            app_config,
        )

    def get_langchain_tools_by_config(self, tools_config: list[dict]) -> list[BaseTool]:
        """根据工具配置列表创建LangChain工具实例

        Args:
            tools_config: 工具配置列表，每个配置是一个字典，包含工具类型、
            提供者信息和工具参数等

        Returns:
            list[BaseTool]: 创建好的LangChain工具实例列表

        """
        # 初始化工具列表
        tools = []
        # 遍历草稿配置中的工具列表
        for tool in tools_config:
            # 处理内置工具
            if tool["type"] == "builtin_tool":
                # 获取内置工具实例
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],  # 提供者ID
                    tool["tool"]["name"],  # 工具名称
                )
                if not builtin_tool:
                    continue  # 如果工具不存在则跳过
                # 将工具实例添加到工具列表
                tools.append(
                    builtin_tool(**tool["tool"]["params"]),
                )  # 使用传入的参数初始化工具
            else:
                # 处理API工具
                api_tool = self.get(
                    ApiTool,
                    tool["tool"]["id"],
                )  # 从数据库获取API工具配置
                if not api_tool:
                    continue  # 如果工具不存在则跳过
                # 创建API工具实例并添加到工具列表
                tools.append(
                    self.api_provider_manager.get_tool(
                        ToolEntity(  # 构建工具实体对象
                            id=str(api_tool.id),
                            name=api_tool.name,
                            url=api_tool.url,
                            method=api_tool.method,
                            description=api_tool.description,
                            headers=api_tool.provider.headers,
                            parameters=api_tool.parameters,
                        ),
                    ),
                )

        return tools  # 返回创建好的工具列表

    @classmethod
    def _process_and_transformer_app_config(
        cls,
        tools: list[dict],
        workflows: list[dict],
        datasets: list[dict],
        app_config: AppConfig | AppConfigVersion,
    ) -> dict[str, Any]:
        """将应用配置数据转换为字典格式

        Args:
            cls: 类对象
            tools: 工具配置列表
            workflows: 工作流配置列表
            datasets: 知识库配置列表
            app_config: 应用配置对象，可以是AppConfig或AppConfigVersion实例

        Returns:
            dict[str, Any]: 包含完整应用配置信息的字典，包括：
                - id: 应用配置ID
                - model_config: 模型配置
                - dialog_round: 对话轮次
                - preset_prompt: 预设提示词
                - tools: 工具列表
                - workflows: 工作流列表
                - datasets: 知识库列表
                - retrieval_config: 检索配置
                - long_term_memory: 长期记忆配置
                - opening_statement: 开场白
                - opening_questions: 开场问题
                - suggested_after_answer: 回答后的建议
                - speech_to_text: 语音转文本配置
                - text_to_speech: 文本转语音配置
                - review_config: 审核配置
                - created_at: 创建时间戳
                - updated_at: 更新时间戳

        """
        return {
            "id": str(app_config.id),
            "model_config": app_config.model_config,
            "dialog_round": app_config.dialog_round,
            "preset_prompt": app_config.preset_prompt,
            "tools": tools,
            "workflows": workflows,
            "datasets": datasets,
            "retrieval_config": app_config.retrieval_config,
            "long_term_memory": app_config.long_term_memory,
            "opening_statement": app_config.opening_statement,
            "opening_questions": app_config.opening_questions,
            "suggested_after_answer": app_config.suggested_after_answer,
            "speech_to_text": app_config.speech_to_text,
            "text_to_speech": app_config.text_to_speech,
            "review_config": app_config.review_config,
            "created_at": datetime_to_timestamp(app_config.created_at),
            "updated_at": datetime_to_timestamp(app_config.updated_at),
        }

    def _process_and_validate_tools(
        self,
        origin_tools: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """处理和验证工具配置

        Args:
            origin_tools: 原始工具配置列表，每个工具是一个字典，
            包含type、provider_id、tool_id等信息

        Returns:
            tuple[list[dict], list[dict]]: 返回两个列表
                - 第一个列表是处理后的工具信息，用于展示
                - 第二个列表是验证后的工具配置，用于实际使用

        """
        # 初始化验证后的工具列表和返回的工具列表
        validate_tools = []  # 存储验证通过的工具配置
        tools = []  # 存储处理后的工具信息，用于前端展示

        # 遍历处理每个工具
        for tool in origin_tools:
            # 处理内置工具
            if tool["type"] == "builtin_tool":
                # 获取工具提供者
                provider_entity = self.builtin_provider_manager.get_provider(
                    tool["provider_id"],
                )
                if not provider_entity:
                    continue  # 如果提供者不存在，跳过该工具

                # 获取工具实体
                tool_entity = provider_entity.get_tool_entity(tool["tool_id"])
                if not tool_entity:
                    continue  # 如果工具实体不存在，跳过该工具

                # 验证工具参数
                param_keys = {
                    param.name for param in tool_entity.params
                }  # 获取所有必需的参数名
                params = tool["params"]
                # 如果提供的参数与必需参数不匹配，使用默认参数
                if set(tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }

                # 添加验证后的工具配置
                validate_tools.append({**tool, "params": params})
                # 构建返回的工具信息，包含提供者和工具的详细信息
                tools.append(
                    {
                        "type": "builtin_tool",
                        "provider": {
                            "id": provider_entity.name,
                            "name": provider_entity.name,
                            "label": provider_entity.provider_entity.label,
                            "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                        },
                        "tool": {
                            "id": tool_entity.name,
                            "name": tool_entity.name,
                            "label": tool_entity.label,
                            "description": tool_entity.description,
                            "params": tool["params"],
                        },
                    },
                )
            # 处理API工具
            elif tool["type"] == "api_tool":
                # 查询API工具记录
                tool_record = (
                    self.db.session.query(ApiTool)
                    .filter(
                        ApiTool.provider_id == tool["provider_id"],
                        ApiTool.name == tool["tool_id"],
                    )
                    .one_or_none()
                )
                if not tool_record:
                    continue  # 如果工具记录不存在，跳过该工具

                # 添加验证后的工具配置（API工具不需要修改参数）
                validate_tools.append(tool)
                # 获取工具提供者信息
                provider = tool_record.provider
                # 构建返回的工具信息，包含提供者和工具的详细信息
                tools.append(
                    {
                        "type": "api_tool",
                        "provider": {
                            "id": str(provider.id),
                            "name": provider.name,
                            "label": provider.name,
                            "icon": provider.icon,
                            "description": provider.description,
                        },
                        "tool": {
                            "id": str(tool_record.id),
                            "name": tool_record.name,
                            "label": tool_record.name,
                            "description": tool_record.description,
                            "params": {},
                        },
                    },
                )

        return tools, validate_tools

    def _process_and_validate_datasets(
        self,
        origin_datasets: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """处理和验证知识库配置

        Args:
            origin_datasets: 原始知识库ID列表，需要验证的知识库ID集合

        Returns:
            tuple[list[dict], list[dict]]:
                - 第一个元素为处理后的知识库信息列表，
                包含id、name、icon、description等字段
                - 第二个元素为验证通过的知识库ID列表

        """
        # 初始化处理后的知识库列表
        datasets = []

        # 查询数据库中所有相关的知识库记录
        dataset_records = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(origin_datasets),
            )
            .all()
        )

        # 构建知识库ID到记录的映射，便于快速查找
        dataset_dict = {
            str(dataset_record.id): dataset_record for dataset_record in dataset_records
        }

        # 将存在的知识库ID转换为集合，提高查找效率
        dataset_sets = set(dataset_dict.keys())

        # 筛选出存在于数据库中的知识库ID
        validate_datasets = [
            dataset_id for dataset_id in origin_datasets if dataset_id in dataset_sets
        ]

        # 构建返回的知识库信息列表
        for dataset_id in validate_datasets:
            dataset_record = dataset_dict.get(str(dataset_id))
            datasets.append(
                {
                    "id": str(dataset_id),  # 知识库ID
                    "name": dataset_record.name,  # 知识库名称
                    "icon": dataset_record.icon,  # 知识库图标
                    "description": dataset_record.description,  # 知识库描述
                },
            )

        return datasets, validate_datasets
