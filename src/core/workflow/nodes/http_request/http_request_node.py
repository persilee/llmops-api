import requests
from langchain_core.runnables import RunnableConfig

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.http_request.http_request_entity import (
    HttpRequestInputType,
    HttpRequestMethod,
    HttpRequestNodeData,
)
from src.core.workflow.utils.helper import extract_variables_from_state


class HttpRequestNode(BaseNode):
    """HTTP请求节点类，用于执行HTTP请求并获取响应。

    该类继承自BaseNode，实现了HTTP请求节点的核心功能：
    - 支持多种HTTP方法（GET、POST、PUT、PATCH、DELETE、HEAD、OPTIONS）
    - 支持自定义请求头、URL参数和请求体
    - 处理HTTP响应并返回状态码和响应文本
    - 将请求结果封装为NodeResult对象返回

    Attributes:
        node_data (HttpRequestNodeData): 包含HTTP请求节点的配置信息，
        包括URL、请求方法、请求头等

    """

    node_data: HttpRequestNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
    ) -> WorkflowState:
        """执行HTTP请求节点的核心方法

        Args:
            state: 工作流状态对象，包含当前节点的输入数据
            config: 可选的运行配置参数

        Returns:
            WorkflowState: 包含节点执行结果的工作流状态对象

        """
        # 1. 从工作流状态中提取节点输入变量字典
        _inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. 初始化并构建请求数据结构，包含params、headers和body
        inputs_dict = {
            HttpRequestInputType.PARAMS: {},  # URL参数
            HttpRequestInputType.HEADERS: {},  # 请求头
            HttpRequestInputType.BODY: {},  # 请求体
        }
        # 遍历所有输入配置，将提取的变量值按类型分类存储
        for input in self.node_data.inputs:
            inputs_dict[input.meta.get("type")][input.name] = _inputs_dict.get(
                input.name,
            )

        # 3. 创建HTTP请求方法映射字典，支持多种HTTP方法
        request_methods = {
            HttpRequestMethod.GET: requests.get,
            HttpRequestMethod.POST: requests.post,
            HttpRequestMethod.PUT: requests.put,
            HttpRequestMethod.PATCH: requests.patch,
            HttpRequestMethod.DELETE: requests.delete,
            HttpRequestMethod.HEAD: requests.head,
            HttpRequestMethod.OPTIONS: requests.options,
        }

        # 4. 根据配置的请求方法获取对应的requests函数
        request_method = request_methods[self.node_data.method]
        if self.node_data.method == HttpRequestMethod.GET:
            # GET请求只包含headers和params
            response = request_method(
                self.node_data.url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
            )
        else:
            # 5. 其他请求方法（POST、PUT等）需要携带请求体
            response = request_method(
                self.node_data.url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
                data=inputs_dict[HttpRequestInputType.BODY],
            )

        # 6. 从响应对象中提取响应文本和状态码
        text = response.text
        status_code = response.status_code

        # 7. 构建输出数据结构，包含响应文本和状态码
        outputs = {"text": text, "status_code": status_code}

        # 8. 创建并返回包含节点执行结果的工作流状态对象
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,  # 节点配置数据
                    status=NodeStatus.SUCCEEDED,  # 执行状态
                    inputs=inputs_dict,  # 输入参数
                    outputs=outputs,  # 输出结果
                ),
            ],
        }
