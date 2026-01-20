import time
from typing import Any

from jinja2 import Template
from langchain_core.runnables import RunnableConfig

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.llm.llm_entity import LLMNodeData
from src.core.workflow.utils.helper import extract_variables_from_state


class LLMNode(BaseNode):
    """LLM节点类，用于处理大语言模型相关的任务。

    该类继承自BaseNode，实现了与OpenAI语言模型的交互功能。主要职责包括：
    - 接收和处理输入变量
    - 使用Jinja2模板引擎渲染提示词
    - 调用OpenAI API生成内容
    - 处理和格式化输出结果

    Attributes:
        node_data (LLMNodeData): 包含LLM节点的配置数据，包括：
            - inputs: 输入变量配置
            - prompt: 提示词模板
            - language_model_config: 模型配置参数
            - outputs: 输出变量配置

    """

    node_data: LLMNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> WorkflowState:
        """执行LLM节点的主要逻辑。

        Args:
            state (WorkflowState): 当前工作流的状态，包含所有节点的输入输出数据
            config (RunnableConfig | None, optional): 可选的运行配置，用于控制执行行为。
            **kwargs (Any): 额外的关键字参数

        Returns:
            WorkflowState: 更新后的工作流状态，包含：
                - node_results: 包含节点执行结果的列表，每个结果包括：
                    - node_data: 节点配置数据
                    - status: 节点执行状态（成功/失败）
                    - inputs: 节点的输入数据
                    - outputs: 节点的输出数据

        执行流程：
            1. 从工作流状态中提取所需的输入变量
            2. 使用Jinja2模板引擎渲染提示词模板
            3. 初始化OpenAI聊天模型并调用生成内容
            4. 处理输出结果，使用配置的输出变量名或默认的"output"
            5. 返回包含节点执行结果的工作流状态

        """
        # 记录开始时间
        start_at = time.perf_counter()
        # 从工作流状态中提取所需的输入变量
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 使用Jinja2模板引擎渲染提示词模板
        template = Template(self.node_data.prompt)
        prompt_value = template.render(**inputs_dict)

        # 初始化OpenAI聊天模型
        # 使用配置中的模型名称，默认为gpt-4o-mini
        # 同时传入其他模型参数配置
        from app.http.module import injector
        from src.service import LLMModelService

        llm_model_service = injector.get(LLMModelService)
        llm = llm_model_service.load_language_model(
            self.node_data.language_model_config,
        )

        # 调用模型生成内容
        content = ""
        for chunk in llm.stream(prompt_value):
            content += chunk.content

        # 准备输出结果
        outputs = {}
        # 如果节点配置了输出变量，使用配置的变量名
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = content
        # 否则使用默认的"output"作为输出变量名
        else:
            outputs["output"] = content

        # 返回包含节点执行结果的工作流状态
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,  # 节点配置数据
                    status=NodeStatus.SUCCEEDED,  # 执行状态：成功
                    inputs=inputs_dict,  # 输入数据
                    outputs=outputs,  # 输出数据
                    latency=(time.perf_counter() - start_at),  # 执行耗时
                ),
            ],
        }
