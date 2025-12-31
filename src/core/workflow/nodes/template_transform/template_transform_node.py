import time
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
    """模板转换节点类，用于处理基于Jinja2模板的文本转换。

    该节点继承自BaseNode，主要功能是：
    1. 接收输入变量和预定义的Jinja2模板
    2. 使用输入变量渲染模板
    3. 输出渲染后的结果

    Attributes:
        node_data (TemplateTransformNodeData): 节点配置数据，包含模板定义和输入变量配置

    """

    node_data: TemplateTransformNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> WorkflowState:
        """执行模板转换节点的核心逻辑

        Args:
            state: 工作流状态对象，包含当前节点的输入数据
            config: 可选的运行配置，默认为None
            **kwargs: 额外的关键字参数

        Returns:
            WorkflowState: 包含节点执行结果的工作流状态，其中包含：
                - node_results: 节点执行结果列表，包含转换后的输出数据

        """
        # 记录开始时间
        start_at = time.perf_counter()
        # 从工作流状态中提取所需的输入变量
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 创建Jinja2模板对象
        template = Template(self.node_data.template)
        # 使用输入变量渲染模板
        template_value = template.render(**inputs_dict)

        # 构建输出字典，包含渲染后的模板值
        outputs = {"output": template_value}

        # 返回包含节点执行结果的工作流状态
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                ),
            ],
        }
