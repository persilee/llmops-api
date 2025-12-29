from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Output

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.end.end_entity import EndNodeData
from src.core.workflow.utils.helper import extract_variables_from_state


class EndNode(BaseNode):
    node_data: EndNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Output:
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
