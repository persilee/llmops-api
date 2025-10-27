from collections.abc import Callable
from dataclasses import dataclass

import requests
from injector import inject
from langchain.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from src.core.tools.api_tool.entities.openapi_schema import (
    ParameterIn,
    ParameterTypeMap,
)
from src.core.tools.api_tool.entities.tool_entity import ToolEntity


@inject
@dataclass
class ApiProviderManager(BaseModel):
    """API提供者管理器，负责管理和创建API工具。

    主要功能：
    1. 从工具实体创建可调用的工具函数
    2. 根据参数配置动态创建Pydantic模型
    3. 生成符合Langchain标准的工具实例

    该类作为API工具的核心管理组件，处理工具的创建、参数验证和请求执行。
    """

    @classmethod
    def _create_tool_func_from_entity(cls, tool_entity: ToolEntity) -> Callable:
        """从工具实体创建工具函数。

        Args:
            tool_entity (ToolEntity): 工具实体对象，包含API的配置信息，包括：
                - method: HTTP方法（GET、POST等）
                - url: API的URL模板
                - parameters: 参数配置列表
                - headers: 请求头配置列表

        Returns:
            Callable: 返回一个工具函数，该函数接受关键字参数并发送HTTP请求。
                函数签名：tool_func(**kwargs: dict) -> str
                其中：
                - kwargs: 动态参数字典，参数名和值根据API配置确定
                - 返回值: API响应的文本内容

        Note:
            创建的工具函数会自动处理以下类型的参数：
            - 路径参数 (PATH): 用于URL格式化
            - 查询参数 (QUERY): 作为URL查询字符串
            - 请求头参数 (HEADER): 添加到HTTP请求头
            - Cookie参数 (COOKIE): 添加到请求的Cookie
            - 请求体参数 (REQUEST_BODY): 作为JSON请求体

            请求超时设置为连接超时3.05秒，读取超时27秒。

        """

        def tool_func(**kwargs: dict) -> str:
            # 初始化参数字典，用于存储不同位置的参数
            parameters = {
                ParameterIn.PATH: {},  # URL路径参数
                ParameterIn.QUERY: {},  # URL查询参数
                ParameterIn.HEADER: {},  # HTTP请求头参数
                ParameterIn.COOKIE: {},  # Cookie参数
                ParameterIn.REQUEST_BODY: {},  # 请求体参数
            }

            # 创建参数映射字典，将参数名映射到参数配置
            parameter_map = {
                parameter.get("name"): parameter for parameter in tool_entity.parameters
            }
            # 创建请求头映射字典，将请求头键映射到对应的值
            header_map = {
                header.get("key"): header.get("value") for header in tool_entity.headers
            }

            # 遍历传入的关键字参数
            for key, value in kwargs.items():
                # 获取参数配置信息
                parameter = parameter_map.get(key)
                # 如果参数不存在于配置中，跳过
                if parameter is None:
                    continue

                # 根据参数位置将参数值存入对应的字典中
                # 默认使用QUERY位置
                parameters[parameter.get("in", ParameterIn.QUERY)][key] = value

            # 发送HTTP请求
            return requests.request(
                method=tool_entity.method,  # HTTP方法（GET、POST等）
                url=tool_entity.url.format(
                    **parameters[ParameterIn.PATH],
                ),  # 格式化URL，填充路径参数
                params=parameters[ParameterIn.QUERY],  # 设置查询参数
                json=parameters[ParameterIn.REQUEST_BODY],  # 设置请求体
                headers={
                    **header_map,
                    **parameters[ParameterIn.HEADER],
                },  # 合并默认请求头和参数请求头
                cookies=parameters[ParameterIn.COOKIE],  # 设置Cookie
                timeout=(3.05, 27),  # 设置超时时间（连接超时，读取超时）
            ).text  # 返回响应文本

        return tool_func

    @classmethod
    def _create_model_from_parameters(cls, parameters: list[dict]) -> type[BaseModel]:
        """根据参数列表动态创建 Pydantic 模型。

        Args:
            parameters (list[dict]): 参数列表，每个参数包含以下字段：
                - name: 参数名称
                - type: 参数类型
                - required: 是否必需（默认为 True）
                - description: 参数描述（默认为空字符串）

        Returns:
            type[BaseModel]: 动态创建的 Pydantic 模型类

        """
        # 初始化字段字典
        fields = {}
        # 遍历每个参数
        for parameter in parameters:
            # 获取参数名称
            field_name = parameter.get("name")
            # 获取参数类型，如果未找到则默认为 str
            field_type = ParameterTypeMap.get(parameter.get("type"), str)
            # 获取是否必需，默认为 True
            field_required = parameter.get("required", True)
            # 获取参数描述，默认为空字符串
            field_description = parameter.get("description", "")

            # 构建字段定义
            fields[field_name] = (
                # 如果是必需字段则使用原类型，否则添加 Optional
                field_type if field_required else field_type | None,
                # 添加字段描述
                Field(description=field_description),
            )

        # 使用 create_model 创建动态模型
        return create_model("DynamicModel", **fields)

    def get_tool(self, tool_entity: ToolEntity) -> BaseTool:
        """根据工具实体创建一个结构化工具实例。

        Args:
            tool_entity (ToolEntity): 包含工具配置信息的实体对象，包括：
                - id: 工具的唯一标识符
                - name: 工具名称
                - description: 工具描述
                - parameters: 工具参数列表

        Returns:
            BaseTool: 返回一个配置好的结构化工具实例，包含：
                - func: 从工具实体创建的可调用函数
                - name: 格式为"{id}_{name}"的工具名称
                - description: 工具的描述信息
                - args_schema: 基于参数列表创建的Pydantic模型

        """
        return StructuredTool.from_function(
            func=self._create_tool_func_from_entity(tool_entity),
            name=f"{tool_entity.id}_{tool_entity.name}",
            description=tool_entity.description,
            args_schema=self._create_model_from_parameters(tool_entity.parameters),
        )
