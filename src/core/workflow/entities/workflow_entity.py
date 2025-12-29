import re
from typing import Annotated, Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.core.workflow.entities.edge_entity import BaseEdgeData
from src.core.workflow.entities.node_entity import BaseNodeData, NodeResult, NodeType
from src.exception.exception import ValidateErrorException

WORKFLOW_CONFIG_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"
WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH = 1024


def _process_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left = left or {}
    right = right or {}

    return {**left, **right}


def _process_node_results(
    left: list[NodeResult],
    right: list[NodeResult],
) -> list[NodeResult]:
    left = left or []
    right = right or []

    return left + right


class WorkflowConfig(BaseModel):
    account_id: UUID  # 工作流所属的账户ID
    name: str = ""  # 工作流名称，用于标识和展示工作流，必须是英文
    description: str = ""  # 工作流描述，详细说明工作流的功能和用途
    nodes: list[BaseNodeData] = Field(
        default_factory=list,
    )  # 工作流节点列表，包含所有节点的配置信息
    edges: list[BaseNodeData] = Field(
        default_factory=list,
    )  # 工作流边列表，定义节点之间的连接关系

    @classmethod
    def _validate_basic_info(cls, values: dict[str, Any]) -> None:
        """验证基本信息"""
        name = values.get("name")
        if not name or not re.match(WORKFLOW_CONFIG_NAME_PATTERN, name):
            error_msg = "工作流名字仅支持字母、数字和下划线，且以字母/下划线为开头"
            raise ValidateErrorException(error_msg)

        description = values.get("description")
        if not description or len(description) > WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH:
            error_msg = "工作流描述信息长度不能超过1024个字符"
            raise ValidateErrorException(error_msg)

    @classmethod
    def _validate_nodes(cls, nodes: list[dict]) -> dict[UUID, BaseNodeData]:
        """验证节点信息"""
        if not isinstance(nodes, list) or len(nodes) <= 0:
            error_msg = "工作流节点列表信息错误，请核实后重试"
            raise ValidateErrorException(error_msg)

        from src.core.workflow.nodes import (
            CodeNodeData,
            DatasetRetrievalNodeData,
            EndNodeData,
            HttpRequestNodeData,
            LLMNodeData,
            StartNodeData,
            TemplateTransformNodeData,
            ToolNodeData,
        )

        node_data_classes = {
            NodeType.START: StartNodeData,
            NodeType.END: EndNodeData,
            NodeType.LLM: LLMNodeData,
            NodeType.TEMPLATE_TRANSFORM: TemplateTransformNodeData,
            NodeType.DATASET_RETRIEVAL: DatasetRetrievalNodeData,
            NodeType.CODE: CodeNodeData,
            NodeType.TOOL: ToolNodeData,
            NodeType.HTTP_REQUEST: HttpRequestNodeData,
        }

        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0

        for node in nodes:
            if not isinstance(node, dict):
                error_msg = "工作流节点数据类型出错，请核实后重试"
                raise ValidateErrorException(error_msg)

            node_type = node.get("node_type", "")
            node_data_cls = node_data_classes.get(node_type)
            if not node_data_cls:
                error_msg = "工作流节点类型出错，请核实后重试"
                raise ValidateErrorException(error_msg)

            node_data = node_data_cls(**node)

            if node_data.node_type == NodeType.START:
                if start_nodes >= 1:
                    error_msg = "工作流中只允许有1个开始节点"
                    raise ValidateErrorException(error_msg)
                start_nodes += 1
            elif node_data.node_type == NodeType.END:
                if end_nodes >= 1:
                    error_msg = "工作流中只允许有1个结束节点"
                    raise ValidateErrorException(error_msg)
                end_nodes += 1

            if node_data.id in node_data_dict:
                error_msg = "工作流节点id必须唯一，请核实后重试"
                raise ValidateErrorException(error_msg)

            if any(
                item.title.strip() == node_data.title.strip()
                for item in node_data_dict.values()
            ):
                error_msg = "工作流节点title必须唯一，请核实后重试"
                raise ValidateErrorException(error_msg)

            node_data_dict[node_data.id] = node_data

        return node_data_dict

    @classmethod
    def _validate_edges(
        cls,
        edges: list[dict],
        node_data_dict: dict[UUID, BaseNodeData],
    ) -> dict[UUID, BaseEdgeData]:
        """验证边信息"""
        if not isinstance(edges, list) or len(edges) <= 0:
            error_msg = "工作流边列表信息错误，请核实后重试"
            raise ValidateErrorException(error_msg)

        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            if not isinstance(edge, dict):
                error_msg = "工作流边数据类型出错，请核实后重试"
                raise ValidateErrorException(error_msg)

            edge_data = BaseEdgeData(**edge)

            if edge_data.id in edge_data_dict:
                error_msg = "工作流边数据id必须唯一，请核实后重试"
                raise ValidateErrorException(error_msg)

            if (
                edge_data.source not in node_data_dict
                or edge_data.source_type != node_data_dict[edge_data.source].node_type
                or edge_data.target not in node_data_dict
                or edge_data.target_type != node_data_dict[edge_data.target].node_type
            ):
                error_msg = "工作流边起点/终点对应的节点不存在或类型错误，请核实后重试"
                raise ValidateErrorException(error_msg)

            if any(
                item.source == edge_data.source
                and item.target == edge_data.target
                and item.source_handle_id == edge_data.source_handle_id
                for item in edge_data_dict.values()
            ):
                error_msg = "工作流边数据不能重复添加"
                raise ValidateErrorException(error_msg)

            edge_data_dict[edge_data.id] = edge_data

        return edge_data_dict

    @classmethod
    def _validate_graph_structure(
        cls,
        node_data_dict: dict[UUID, BaseNodeData],
        edge_data_dict: dict[UUID, BaseEdgeData],
    ) -> None:
        """验证图结构"""
        adj_list = cls._build_adj_list(edge_data_dict.values())
        reverse_adj_list = cls._build_reverse_adj_list(edge_data_dict.values())
        in_degree, out_degree = cls._build_degrees(edge_data_dict.values())

        start_nodes = [
            node_data
            for node_data in node_data_dict.values()
            if in_degree[node_data.id] == 0
        ]
        end_nodes = [
            node_data
            for node_data in node_data_dict.values()
            if out_degree[node_data.id] == 0
        ]

        if (
            len(start_nodes) != 1
            or len(end_nodes) != 1
            or start_nodes[0].node_type != NodeType.START
            or end_nodes[0].node_type != NodeType.END
        ):
            error_msg = "工作流中有且只有一个开始/结束节点作为图结构的起点和终点"
            raise ValidateErrorException(error_msg)

        start_node_data = start_nodes[0]

        if not cls._is_connected(adj_list, start_node_data.id):
            error_msg = "工作流中存在不可到达节点，图不联通，请核实后重试"
            raise ValidateErrorException(error_msg)

        if cls._is_cycle(node_data_dict.values(), adj_list, in_degree):
            error_msg = "工作流中存在环路，请核实后重试"
            raise ValidateErrorException(error_msg)

        cls._validate_inputs_ref(node_data_dict, reverse_adj_list)

    @classmethod
    @model_validator(pre=True)
    def validate_workflow_config(cls, values: dict[str, Any]) -> dict[str, Any]:
        cls._validate_basic_info(values)

        nodes = values.get("nodes", [])
        edges = values.get("edges", [])

        node_data_dict = cls._validate_nodes(nodes)
        edge_data_dict = cls._validate_edges(edges, node_data_dict)

        cls._validate_graph_structure(node_data_dict, edge_data_dict)

        values["nodes"] = list(node_data_dict.values())
        values["edges"] = list(edge_data_dict.values())

        return values


class WorkflowState(TypedDict):
    inputs: Annotated[dict[str, Any], _process_dict]
    outputs: Annotated[dict[str, Any], _process_dict]
    node_results: Annotated[list[NodeResult], _process_node_results]
