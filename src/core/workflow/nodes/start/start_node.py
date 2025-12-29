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
    node_data: StartNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Output:
        inputs = self.node_data.inputs

        outputs = {}
        for input_data in inputs:
            input_value = state["inputs"].get(input_data.name, None)

            if input_value is None:
                if input_data.required:
                    error_msg = f"工作流参数 {input_data.name} 未提供"
                    raise FailException(error_msg)
                input_value = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(input_data.type)

            outputs[input_data.name] = input_value

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=state["inputs"],
                    outputs=outputs,
                ),
            ],
        }
