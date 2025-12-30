from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Output

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.end.end_entity import EndNodeData
from src.core.workflow.utils.helper import extract_variables_from_state


class EndNode(BaseNode):
    """工作流结束节点类。

    用于处理工作流的最终输出，从工作流状态中提取指定的输出变量，
    并将它们作为最终结果返回。这是工作流执行的最后一步。

    Attributes:
        node_data (EndNodeData): 节点的配置数据，包含输出变量的定义

    """

    node_data: EndNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Output:
        """执行结束节点的逻辑，处理工作流的最终输出。

        Args:
            state (WorkflowState): 当前工作流的状态，包含所有节点的执行结果和中间变量
            config (RunnableConfig | None): 可选的运行配置，用于控制执行行为
            **kwargs (Any): 额外的关键字参数，用于扩展功能

        Returns:
            Output: 包含以下字段的字典：
                - outputs (dict): 从工作流状态中提取的输出变量
                - node_results (list): 包含节点执行结果的列表，包括：
                    * node_data: 节点的配置数据
                    * status: 节点执行状态（成功/失败）
                    * inputs: 节点输入数据（对于结束节点为空）
                    * outputs: 节点输出数据

        """
        outputs_dict = extract_variables_from_state(self.node_data.outputs, state)

        return {
            "outputs": outputs_dict,
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs={},
                    outputs=outputs_dict,
                ),
            ],
        }
