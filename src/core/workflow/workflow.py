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

NodeClasses = {
    NodeType.START: StartNode,
    NodeType.END: EndNode,
    NodeType.LLM: LLMNode,
    NodeType.TEMPLATE_TRANSFORM: TemplateTransformNode,
    NodeType.CODE: CodeNode,
    NodeType.TOOL: ToolNode,
    NodeType.HTTP_REQUEST: HttpRequestNode,
}


class Workflow(BaseTool):
    _workflow_config: WorkflowConfig = PrivateAttr(None)
    _workflow: CompiledStateGraph = PrivateAttr(None)

    def __init__(self, workflow_config: WorkflowConfig, **kwargs: Any) -> None:
        super().__init__(
            name=workflow_config.name,
            description=workflow_config.description,
            args_schema=self._build_args_schema(workflow_config),
            **kwargs,
        )
        self._workflow_config = workflow_config
        self._workflow = self._build_workflow()

    def _build_args_schema(self, workflow_config: WorkflowConfig) -> type[BaseModel]:
        fields = {}
        inputs = next(
            (
                node.inputs
                for node in workflow_config.nodes
                if node.node_type == NodeType.START
            ),
            [],
        )

        for input in inputs:
            field_name = input.name
            field_type = VARIABLE_TYPE_MAP.get(input.type, str)
            field_required = input.required
            field_description = input.description

            fields[field_name] = (
                field_type if field_required else field_type | None,
                Field(description=field_description),
            )

        return create_model("DynamicModel", **fields)

    def _create_node(self, node: BaseNodeData) -> Any:
        """创建工作流节点"""
        node_type = node.node_type.value
        node_flag = f"{node_type}_{node.id}"

        node_creators = {
            NodeType.START: lambda: NodeClasses[NodeType.START](node_data=node),
            NodeType.LLM: lambda: NodeClasses[NodeType.LLM](node_data=node),
            NodeType.TEMPLATE_TRANSFORM: lambda: NodeClasses[
                NodeType.TEMPLATE_TRANSFORM
            ](node_data=node),
            NodeType.DATASET_RETRIEVAL: lambda: NodeClasses[NodeType.DATASET_RETRIEVAL](
                flask_app=current_app._get_current_object(),  # noqa: SLF001
                account_id=self._workflow_config.account_id,
                node_data=node,
            ),
            NodeType.CODE: lambda: NodeClasses[NodeType.CODE](node_data=node),
            NodeType.TOOL: lambda: NodeClasses[NodeType.TOOL](node_data=node),
            NodeType.HTTP_REQUEST: lambda: NodeClasses[NodeType.HTTP_REQUEST](
                node_data=node,
            ),
            NodeType.END: lambda: NodeClasses[NodeType.END](node_data=node),
        }

        creator = node_creators.get(node_type)
        if creator is None:
            error_msg = f"节点类型 {node_type} 不存在"
            raise ValueError(error_msg)

        return node_flag, creator()

    def _build_workflow(self) -> CompiledStateGraph:
        graph = StateGraph(WorkflowState)

        for node in self._workflow_config.nodes:
            node_flag, node_instance = self._create_node(node)
            graph.add_node(node_flag, node_instance)

        parallel_edges = {}
        start_node = ""
        end_node = ""
        for edge in self._workflow_config.edges:
            source_node = f"{edge.source_type.value}_{edge.source}"
            target_node = f"{edge.target_type.value}_{edge.target}"

            parallel_edges.setdefault(target_node, []).append(source_node)

            if edge.source_type == NodeType.START:
                start_node = f"{edge.source_type.value}_{edge.source}"
            elif edge.target_type == NodeType.END:
                end_node = f"{edge.target_type.value}_{edge.target}"

        graph.set_entry_point(start_node)
        graph.set_finish_point(end_node)

        for target_node, sources in parallel_edges.items():
            graph.add_edge(sources, target_node)

        return graph.compile()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return self._workflow.invoke({"inputs": kwargs})

    def stream(
        self,
        input_data: Input,
        config: RunnableConfig | None = None,
        **kwargs: Any | None,
    ) -> Iterator[Output]:
        return self._workflow.stream({"inputs": input_data})
