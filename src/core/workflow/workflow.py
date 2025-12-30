from collections.abc import Iterator
from typing import Any

from flask import current_app
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Input, Output
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field, PrivateAttr, create_model

from src.core.workflow.entities.node_entity import BaseNodeData, NodeType
from src.core.workflow.entities.variable_entity import VARIABLE_TYPE_MAP
from src.core.workflow.entities.workflow_entity import WorkflowConfig, WorkflowState
from src.core.workflow.nodes.code.code_node import CodeNode
from src.core.workflow.nodes.end.end_node import EndNode
from src.core.workflow.nodes.http_request.http_request_node import HttpRequestNode
from src.core.workflow.nodes.llm.llm_node import LLMNode
from src.core.workflow.nodes.start.start_node import StartNode
from src.core.workflow.nodes.template_transform.template_transform_node import (
    TemplateTransformNode,
)

# 节点类型映射字典，用于根据节点类型创建对应的节点实例
# 键为节点类型枚举值，值为对应的节点类
NodeClasses = {
    NodeType.START: StartNode,  # 开始节点，工作流的入口点
    NodeType.END: EndNode,  # 结束节点，工作流的出口点
    NodeType.LLM: LLMNode,  # LLM节点，用于处理大语言模型相关任务
    NodeType.TEMPLATE_TRANSFORM: TemplateTransformNode,  # 模板转换节点，用于格式转换
    NodeType.CODE: CodeNode,  # 代码执行节点，用于执行自定义代码逻辑
    NodeType.TOOL: ToolNode,  # 工具节点，用于调用外部工具
    NodeType.HTTP_REQUEST: HttpRequestNode,  # HTTP请求节点，用于发送HTTP请求
}


class Workflow(BaseTool):
    """工作流执行器类，继承自BaseTool，用于管理和执行工作流。

    该类负责：
    1. 加载和管理工作流配置
    2. 构建和编译工作流图
    3. 执行工作流并处理输入输出

    Attributes:
        _workflow_config (WorkflowConfig): 工作流配置对象，包含节点和边的定义
        _workflow (CompiledStateGraph): 编译后的工作流状态图，用于实际执行

    """

    _workflow_config: WorkflowConfig = PrivateAttr(None)
    _workflow: CompiledStateGraph = PrivateAttr(None)

    def __init__(self, workflow_config: WorkflowConfig, **kwargs: Any) -> None:
        """初始化工作流实例

        Args:
            workflow_config: 工作流配置对象，包含工作流的基本信息和节点配置
            **kwargs: 其他可选参数

        """
        # 调用父类BaseTool的初始化方法，设置工具的基本属性
        super().__init__(
            name=workflow_config.name,  # 设置工具名称
            description=workflow_config.description,  # 设置工具描述
            args_schema=self._build_args_schema(workflow_config),  # 构建并设置参数模式
            **kwargs,  # 传递其他可选参数
        )
        # 保存工作流配置到实例变量
        self._workflow_config = workflow_config
        # 构建并保存编译后的工作流图
        self._workflow = self._build_workflow()

    def _build_args_schema(self, workflow_config: WorkflowConfig) -> type[BaseModel]:
        """构建动态参数模式模型

        Args:
            workflow_config (WorkflowConfig): 工作流配置对象，包含所有节点信息

        Returns:
            type[BaseModel]: 动态创建的Pydantic模型类，用于验证工作流输入参数

        该方法执行以下步骤：
        1. 从工作流配置中找到START节点
        2. 获取START节点的输入参数列表
        3. 为每个输入参数创建对应的字段定义
        4. 使用create_model动态生成Pydantic模型

        """
        fields = {}
        # 查找START节点的输入参数配置
        inputs = next(
            (
                node.inputs
                for node in workflow_config.nodes
                if node.node_type == NodeType.START
            ),
            [],
        )

        # 遍历每个输入参数，构建字段定义
        for input in inputs:
            field_name = input.name  # 字段名称
            field_type = VARIABLE_TYPE_MAP.get(input.type, str)  # 字段类型，默认为str
            field_required = input.required  # 是否必填
            field_description = input.description  # 字段描述

            # 创建字段定义，如果是非必填字段则允许None值
            fields[field_name] = (
                field_type if field_required else field_type | None,
                Field(description=field_description),
            )

        # 使用create_model动态创建Pydantic模型类
        return create_model("DynamicModel", **fields)

    def _create_node(self, node: BaseNodeData) -> Any:
        """根据节点数据创建对应的节点实例

        Args:
            node: 基础节点数据，包含节点类型、ID等信息

        Returns:
            tuple: 包含节点标识和节点实例的元组
                - node_flag: 节点标识，格式为"{节点类型}_{节点ID}"
                - node_instance: 创建的节点实例

        Raises:
            ValueError: 当节点类型不存在时抛出异常

        """
        # 获取节点类型值
        node_type = node.node_type.value
        # 生成节点标识，格式为"节点类型_节点ID"
        node_flag = f"{node_type}_{node.id}"

        # 定义节点创建器字典，将节点类型映射到对应的创建函数
        node_creators = {
            # 开始节点创建器
            NodeType.START: lambda: NodeClasses[NodeType.START](node_data=node),
            # LLM节点创建器
            NodeType.LLM: lambda: NodeClasses[NodeType.LLM](node_data=node),
            # 模板转换节点创建器
            NodeType.TEMPLATE_TRANSFORM: lambda: NodeClasses[
                NodeType.TEMPLATE_TRANSFORM
            ](node_data=node),
            # 数据集检索节点创建器，需要额外的flask应用和账户ID参数
            NodeType.DATASET_RETRIEVAL: lambda: NodeClasses[NodeType.DATASET_RETRIEVAL](
                flask_app=current_app._get_current_object(),  # noqa: SLF001
                account_id=self._workflow_config.account_id,
                node_data=node,
            ),
            # 代码节点创建器
            NodeType.CODE: lambda: NodeClasses[NodeType.CODE](node_data=node),
            # 工具节点创建器
            NodeType.TOOL: lambda: NodeClasses[NodeType.TOOL](node_data=node),
            # HTTP请求节点创建器
            NodeType.HTTP_REQUEST: lambda: NodeClasses[NodeType.HTTP_REQUEST](
                node_data=node,
            ),
            # 结束节点创建器
            NodeType.END: lambda: NodeClasses[NodeType.END](node_data=node),
        }

        # 获取对应节点类型的创建器
        creator = node_creators.get(node_type)
        # 如果创建器不存在，说明节点类型无效
        if creator is None:
            error_msg = f"节点类型 {node_type} 不存在"
            raise ValueError(error_msg)

        # 返回节点标识和创建的节点实例
        return node_flag, creator()

    def _build_workflow(self) -> CompiledStateGraph:
        """构建工作流状态图。

        该方法负责创建一个完整的工作流状态图，包括：
        1. 初始化基于WorkflowState的状态图
        2. 添加所有工作流节点到图中
        3. 处理节点间的边关系，包括并行边
        4. 设置工作流的入口点和结束点
        5. 编译并返回最终的工作流图

        Returns:
            CompiledStateGraph: 编译完成的工作流状态图，可用于执行工作流

        Raises:
            ValueError: 当工作流配置无效时抛出

        """
        # 创建基于工作流状态的状态图
        graph = StateGraph(WorkflowState)

        # 遍历所有节点并添加到图中
        for node in self._workflow_config.nodes:
            node_flag, node_instance = self._create_node(node)
            graph.add_node(node_flag, node_instance)

        # 初始化并行边集合和起始/结束节点标识
        parallel_edges = {}
        start_node = ""
        end_node = ""

        # 遍历所有边，构建节点间的连接关系
        for edge in self._workflow_config.edges:
            # 构建源节点和目标节点的唯一标识
            source_node = f"{edge.source_type.value}_{edge.source}"
            target_node = f"{edge.target_type.value}_{edge.target}"

            # 记录每个目标节点的所有源节点，用于处理并行边
            parallel_edges.setdefault(target_node, []).append(source_node)

            # 识别并记录起始节点和结束节点
            if edge.source_type == NodeType.START:
                start_node = f"{edge.source_type.value}_{edge.source}"
            elif edge.target_type == NodeType.END:
                end_node = f"{edge.target_type.value}_{edge.target}"

        # 设置工作流的入口点和结束点
        graph.set_entry_point(start_node)
        graph.set_finish_point(end_node)

        # 添加所有边到图中，包括并行边
        for target_node, sources in parallel_edges.items():
            graph.add_edge(sources, target_node)

        # 编译并返回最终的工作流图
        return graph.compile()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """执行工作流的核心方法。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数，将作为工作流的输入数据

        Returns:
            Any: 工作流的执行结果

        """
        return self._workflow.invoke({"inputs": kwargs})

    def stream(
        self,
        input_data: Input,
        config: RunnableConfig | None = None,
        **kwargs: Any | None,
    ) -> Iterator[Output]:
        """流式执行工作流

        Args:
            input_data (Input): 输入数据
            config (RunnableConfig | None): 可选的运行配置，默认为None
            **kwargs (Any | None): 其他可选参数

        Returns:
            Iterator[Output]: 输出数据的迭代器，用于流式获取执行结果

        """
        return self._workflow.stream({"inputs": input_data})
