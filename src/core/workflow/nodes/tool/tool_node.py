import time
from typing import Any

from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from pydantic import PrivateAttr, json

from src.core.tools.api_tool.entities.tool_entity import ToolEntity
from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.tool.tool_entity import ToolNodeData
from src.core.workflow.utils.helper import extract_variables_from_state
from src.exception.exception import FailException, NotFoundException
from src.model.api_tool import ApiTool


class ToolNode(BaseNode):
    """工具节点类，用于在工作流中执行具体的工具操作。

    继承自BaseNode，实现了工具节点的核心功能，包括：
    - 工具的初始化和配置
    - 工具的执行和结果处理
    - 输入输出数据的转换和管理

    Attributes:
        node_data (ToolNodeData): 节点配置数据，包含工具的参数和配置信息
        _tool (BaseTool): 私有属性，存储具体的工具实例

    """

    node_data: ToolNodeData
    _tool: BaseTool = PrivateAttr(None)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """构造函数，完成对内置工具的初始化"""
        # 1.调用父类构造函数完成数据初始化
        super().__init__(*args, **kwargs)

        # 2.导入依赖注入及工具提供者
        from app.http.module import injector

        # 3.判断是内置插件还是API插件，执行不同的操作
        if self.node_data.type == "builtin_tool":
            from src.core.tools.builtin_tools.providers import BuiltinProviderManager

            builtin_provider_manager = injector.get(BuiltinProviderManager)

            # 4.调用内置提供者获取内置插件
            _tool = builtin_provider_manager.get_tool(
                self.node_data.provider_id,
                self.node_data.tool_id,
            )
            if not _tool:
                error_msg = "该内置插件扩展不存在，请核实后重试"
                raise NotFoundException(error_msg)

            self._tool = _tool(**self.node_data.params)
        else:
            # 5.API插件，调用数据库查询记录并创建API插件
            from pkg.sqlalchemy import SQLAlchemy

            db = injector.get(SQLAlchemy)

            # 6.根据传递的提供者名字+工具名字查询工具
            api_tool = (
                db.session.query(ApiTool)
                .filter(
                    ApiTool.provider_id == self.node_data.provider_id,
                    ApiTool.name == self.node_data.tool_id,
                )
                .one_or_none()
            )
            if not api_tool:
                error_msg = "该API扩展插件不存在，请核实重试"
                raise NotFoundException(error_msg)

            # 7.导入API插件提供者

            from src.core.tools.providers.api_provider_manager import ApiProviderManager

            api_provider_manager = injector.get(ApiProviderManager)

            # 8.创建API工具提供者并赋值
            self._tool = api_provider_manager.get_tool(
                ToolEntity(
                    id=str(api_tool.id),
                    name=api_tool.name,
                    url=api_tool.url,
                    method=api_tool.method,
                    description=api_tool.description,
                    headers=api_tool.provider.headers,
                    parameters=api_tool.parameters,
                ),
            )

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
    ) -> WorkflowState:
        """执行工具节点的核心方法

        Args:
            state: 工作流状态对象，包含当前执行上下文
            config: 可选的运行配置参数

        Returns:
            WorkflowState: 包含执行结果的工作流状态

        Raises:
            FailException: 当工具执行失败时抛出

        """
        # 记录开始时间
        start_at = time.perf_counter()
        # 1.提取节点中的输入数据
        # 从工作流状态中提取当前节点所需的输入变量
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2.调用插件并获取结果
        # 使用try-except捕获可能的异常，确保系统稳定性
        try:
            # 调用工具的实际执行方法，传入提取的输入参数
            result = self._tool.invoke(inputs_dict)
        except Exception as e:
            # 构造友好的错误提示信息
            error_msg = "扩展插件执行失败，请稍后尝试"
            # 抛出业务异常，同时保留原始异常信息
            raise FailException(error_msg) from e

        # 3.检测result是否为字符串，如果不是则转换
        # 确保结果为字符串格式，便于后续处理和展示
        if not isinstance(result, str):
            # 3.1[升级更新] 避免汉字被转义
            # 使用json序列化非字符串结果，ensure_ascii=False确保中文字符正常显示
            result = json.dumps(result, ensure_ascii=False)

        # 4.提取并构建输出数据结构
        # 初始化输出字典
        outputs = {}
        # 检查节点是否定义了输出配置
        if self.node_data.outputs:
            # 使用配置的第一个输出变量名作为键
            outputs[self.node_data.outputs[0].name] = result
        else:
            # 如果没有配置输出，使用默认的"text"作为键
            outputs["text"] = result

        # 5.构建响应状态并返回
        # 构造包含执行结果的工作流状态
        return {
            "node_results": [
                NodeResult(
                    # 当前节点的配置数据
                    node_data=self.node_data,
                    # 标记节点执行成功
                    status=NodeStatus.SUCCEEDED,
                    # 记录节点的输入参数
                    inputs=inputs_dict,
                    # 记录节点的输出结果
                    outputs=outputs,
                    # 记录节点执行时间
                    latency=(time.perf_counter() - start_at),
                ),
            ],
        }
