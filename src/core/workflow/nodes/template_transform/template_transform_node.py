from typing import Any

from jinja2 import Template
from langchain_core.runnables import RunnableConfig

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.template_transform.template_transform_entity import (
    TemplateTransformNodeData,
)
from src.core.workflow.utils.helper import extract_variables_from_state


class TemplateTransformNode(BaseNode):
    node_data: TemplateTransformNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> WorkflowState:
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        template = Template(self.node_data.template)
        template_value = template.render(**inputs_dict)

        outputs = {"output": template_value}

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                ),
            ],
        }
