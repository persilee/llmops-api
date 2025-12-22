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
from src.model.app import App, AppConfig, AppConfigVersion
from src.model.dataset import Dataset
from src.service.base_service import BaseService


@inject
@dataclass
class AppConfigService(BaseService):
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    api_provider_manager: ApiProviderManager

    def get_draft_app_config(self, app: App) -> dict[str, Any]:
        # 获取应用的草稿配置
        draft_app_config = app.draft_app_config

        # TODO: 校验 model_config 配置

        tools, validate_tools = self._process_and_validate_tools(draft_app_config.tools)

        if draft_app_config.tools != validate_tools:
            self.update(draft_app_config, tools=validate_tools)

        datasets, validate_datasets = self._process_and_validate_datasets(
            draft_app_config.datasets,
        )

        if set(validate_datasets) != set(draft_app_config.datasets):
            self.update(draft_app_config, datasets=validate_datasets)

        # TODO: 校验工作流数据
        workflows = []

        # 返回完整的草稿配置信息
        return self._process_and_transformer_app_config(
            tools,
            workflows,
            datasets,
            draft_app_config,
        )

    def get_app_config(self, app: App) -> dict[str, Any]:
        pass

    def get_langchain_tools_by_config(self, tools_config: list[dict]) -> list[BaseTool]:
        # 初始化工具列表
        tools = []
        # 遍历草稿配置中的工具列表
        for tool in tools_config:
            # 处理内置工具
            if tool["type"] == "builtin_tool":
                # 获取内置工具实例
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],
                    tool["tool"]["name"],
                )
                if not builtin_tool:
                    continue
                # 将工具实例添加到工具列表
                tools.append(builtin_tool(**tool["tool"]["params"]))
            else:
                # 处理API工具
                api_tool = self.get(ApiTool, tool["tool"]["id"])
                if not api_tool:
                    continue
                # 创建API工具实例并添加到工具列表
                tools.append(
                    self.api_provider_manager.get_tool(
                        ToolEntity(
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

        return tools

    @classmethod
    def _process_and_transformer_app_config(
        cls,
        tools: list[dict],
        workflows: list[dict],
        datasets: list[dict],
        app_config: AppConfig | AppConfigVersion,
    ) -> dict[str, Any]:
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
        # 初始化验证后的工具列表和返回的工具列表
        validate_tools = []
        tools = []

        # 遍历处理每个工具
        for tool in origin_tools:
            # 处理内置工具
            if tool["type"] == "builtin_tool":
                # 获取工具提供者
                provider_entity = self.builtin_provider_manager.get_provider(
                    tool["provider_id"],
                )
                if not provider_entity:
                    continue

                # 获取工具实体
                tool_entity = provider_entity.get_tool_entity(tool["tool_id"])
                if not tool_entity:
                    continue

                # 验证工具参数
                param_keys = {param.name for param in tool_entity.params}
                params = tool["params"]
                # 如果参数不匹配，使用默认参数
                if set(tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }

                # 添加验证后的工具配置
                validate_tools.append({**tool, "params": params})
                # 构建返回的工具信息
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
                        ApiTool.id == tool["tool_id"],
                    )
                    .one_or_none()
                )
                if not tool_record:
                    continue

                # 添加验证后的工具配置
                validate_tools.append(tool)
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
        # 处理知识库配置
        datasets = []
        # 查询所有相关的知识库记录
        dataset_records = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(origin_datasets),
            )
            .all()
        )
        # 构建知识库ID到记录的映射
        dataset_dict = {
            str(dataset_record.id): dataset_record for dataset_record in dataset_records
        }
        dataset_sets = set(dataset_dict.keys())

        # 筛选出存在的知识库ID
        validate_datasets = [
            dataset_id for dataset_id in origin_datasets if dataset_id in dataset_sets
        ]

        # 构建返回的知识库信息
        for dataset_id in validate_datasets:
            dataset_record = dataset_dict.get(str(dataset_id))
            datasets.append(
                {
                    "id": str(dataset_id),
                    "name": dataset_record.name,
                    "icon": dataset_record.icon,
                    "description": dataset_record.description,
                },
            )

        return datasets, validate_datasets
