from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Output

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.start.start_entity import StartNodeData
from src.exception.exception import FailException


class StartNode(BaseNode):
    """工作流起始节点类。

    该类负责处理工作流的起始逻辑，主要功能包括：
    1. 验证输入参数的完整性
    2. 为非必需参数设置默认值
    3. 处理工作流的初始状态

    Attributes:
        node_data (StartNodeData): 节点的配置数据，包含输入参数定义等信息

    """

    node_data: StartNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Output:
        """执行起始节点的逻辑处理。

        Args:
            state (WorkflowState): 工作流状态对象，包含输入参数等信息
            config (RunnableConfig | None, optional): 可选的运行配置。默认为None
            **kwargs (Any): 其他关键字参数

        Returns:
            Output: 包含节点执行结果的字典

        Raises:
            FailException: 当必需参数未提供时抛出异常

        处理流程：
            1. 获取节点的输入配置
            2. 遍历所有输入参数
            3. 检查必需参数是否提供，未提供则抛出异常
            4. 为非必需参数设置默认值
            5. 返回包含处理结果的NodeResult对象

        """
        # 获取节点的输入配置
        inputs = self.node_data.inputs

        # 初始化输出字典
        outputs = {}
        # 遍历所有输入参数
        for input_data in inputs:
            # 从工作流状态中获取输入值，如果不存在则返回None
            input_value = state["inputs"].get(input_data.name, None)

            # 如果输入值为None
            if input_value is None:
                # 检查该参数是否是必需的
                if input_data.required:
                    # 如果是必需参数但未提供，抛出异常
                    error_msg = f"工作流参数 {input_data.name} 未提供"
                    raise FailException(error_msg)
                # 如果不是必需参数，使用该类型的默认值
                input_value = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(input_data.type)

            # 将处理后的值存入输出字典
            outputs[input_data.name] = input_value

        # 返回节点执行结果
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,  # 节点数据
                    status=NodeStatus.SUCCEEDED,  # 执行状态为成功
                    inputs=state["inputs"],  # 原始输入参数
                    outputs=outputs,  # 处理后的输出结果
                ),
            ],
        }
