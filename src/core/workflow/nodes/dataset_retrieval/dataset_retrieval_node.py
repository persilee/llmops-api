import time
from typing import Any
from uuid import UUID

from flask import Flask
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from pydantic import PrivateAttr

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.dataset_retrieval.dataset_retrieval_entity import (
    DatasetRetrievalNodeData,
)
from src.core.workflow.utils.helper import extract_variables_from_state


class DatasetRetrievalNode(BaseNode):
    """知识库检索节点类，用于在工作流中执行知识库检索操作。

    继承自BaseNode，实现了知识库检索的具体功能。该节点使用配置的知识库ID和检索参数，
    通过RetrievalService创建检索工具，用于在工作流中执行知识库检索。
    """

    node_data: DatasetRetrievalNodeData  # 节点配置数据，包含知识库ID和检索配置
    _retrieval_tool: BaseTool = PrivateAttr(None)  # 私有属性，存储知识库检索工具实例

    def __init__(
        self,
        *args: Any,
        flask_app: Flask,  # Flask应用实例，用于创建检索工具
        account_id: UUID,  # 账户ID，用于权限控制和数据隔离
        **kwargs: Any,
    ) -> None:
        """初始化知识库检索节点。

        Args:
            *args: 可变位置参数，传递给父类BaseNode
            flask_app: Flask应用实例，用于创建检索工具
            account_id: 账户ID，用于权限控制和数据隔离
            **kwargs: 可变关键字参数，传递给父类BaseNode

        """
        super().__init__(*args, **kwargs)

        from app.http.module import injector
        from src.service import RetrievalService

        retrieval_service = injector.get(RetrievalService)

        # 使用RetrievalService创建知识库检索工具
        self._retrieval_tool = retrieval_service.create_langchain_tool_from_search(
            flask_app=flask_app,
            dataset_ids=self.node_data.dataset_ids,  # 使用节点配置中的知识库ID列表
            account_id=account_id,  # 使用传入的账户ID
            **self.node_data.retrieval_config.dict(),  # 使用节点配置中的检索参数
        )

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> WorkflowState:
        """执行知识库检索操作

        Args:
            state: 工作流状态对象，包含当前工作流的所有状态信息
            config: 可选的运行配置，默认为None
            **kwargs: 其他关键字参数

        Returns:
            WorkflowState: 包含节点执行结果的工作流状态

        """
        # 记录开始时间
        start_at = time.perf_counter()
        # 从工作流状态中提取输入变量
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 调用检索工具执行知识库检索
        combine_documents = self._retrieval_tool.invoke(inputs_dict)

        # 准备输出结果
        outputs = {}
        if self.node_data.outputs:
            # 如果节点配置了输出，使用配置的输出名称
            outputs[self.node_data.outputs[0].name] = combine_documents
        else:
            # 如果没有配置输出，使用默认名称
            outputs["combine_documents"] = combine_documents

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
