import re
from typing import Annotated, Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.workflow.entities.edge_entity import BaseEdgeData
from src.core.workflow.entities.node_entity import BaseNodeData, NodeResult, NodeType
from src.exception.exception import ValidateErrorException

# 工作流名称的正则表达式模式：必须以字母或下划线开头，只能包含字母、数字和下划线
WORKFLOW_CONFIG_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"
# 工作流描述的最大长度限制：最多允许1024个字符
WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH = 1024


def _process_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """合并两个字典，返回一个新的字典。

    如果两个字典中有相同的键，right字典的值会覆盖left字典的值。

    Args:
        left (dict[str, Any]): 第一个字典，将被合并的基础字典
        right (dict[str, Any]): 第二个字典，其值会覆盖left中的相同键的值

    Returns:
        dict[str, Any]: 合并后的新字典

    """
    left = left or {}
    right = right or {}

    return {**left, **right}


def _process_node_results(
    left: list[NodeResult],
    right: list[NodeResult],
) -> list[NodeResult]:
    """合并两个节点结果列表。

    Args:
        left (list[NodeResult]): 第一个节点结果列表
        right (list[NodeResult]): 第二个节点结果列表

    Returns:
        list[NodeResult]: 合并后的节点结果列表

    """
    left = left or []
    right = right or []

    return left + right


class WorkflowConfig(BaseModel):
    """工作流配置数据模型。

    用于定义和验证工作流的完整配置信息，包括：
    - 基本信息：工作流名称、描述等
    - 节点配置：包含所有节点的具体配置
    - 边配置：定义节点之间的连接关系

    该类提供了完整的验证机制，确保工作流配置的正确性：
    - 基本信息验证（名称格式、描述长度等）
    - 节点配置验证（节点类型、参数等）
    - 边配置验证（连接关系、引用有效性等）
    - 图结构验证（连通性、循环检测等）
    """

    model_config = ConfigDict(
        # 配置 pydantic 使用 any 序列化
        arbitrary_types_allowed=True,
    )

    account_id: UUID  # 工作流所属的账户ID
    account_id: UUID  # 工作流所属的账户ID
    name: str = ""  # 工作流名称，用于标识和展示工作流，必须是英文
    description: str = ""  # 工作流描述，详细说明工作流的功能和用途
    nodes: list[Any] = Field(
        default_factory=list,
    )  # 工作流节点列表，包含所有节点的配置信息
    edges: list[Any] = Field(
        default_factory=list,
    )  # 工作流边列表，定义节点之间的连接关系

    @classmethod
    def _validate_basic_info(cls, values: dict[str, Any]) -> None:
        """验证工作流的基本信息，包括名称和描述

        Args:
            values (dict[str, Any]): 包含工作流基本信息的字典，
            必须包含name和description字段

        Raises:
            ValidateErrorException: 当工作流名称或描述不符合要求时抛出异常
                - 名称不符合正则表达式规则时
                - 描述长度超过限制时

        """
        # 获取并验证工作流名称
        name = values.get("name")
        if not name or not re.match(WORKFLOW_CONFIG_NAME_PATTERN, name):
            error_msg = "工作流名字仅支持字母、数字和下划线，且以字母/下划线为开头"
            raise ValidateErrorException(error_msg)

        # 获取并验证工作流描述
        description = values.get("description")
        if not description or len(description) > WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH:
            error_msg = "工作流描述信息长度不能超过1024个字符"
            raise ValidateErrorException(error_msg)

    @classmethod
    def _validate_nodes(cls, nodes: list[dict]) -> dict[UUID, BaseNodeData]:
        """验证工作流节点配置。

        该方法对工作流中的节点列表进行全面验证，包括：
        - 检查节点列表的基本格式和有效性
        - 验证每个节点的数据类型和类型有效性
        - 确保开始节点和结束节点各只有一个
        - 验证节点ID和标题的唯一性

        Args:
            nodes (list[dict]): 待验证的节点列表，每个节点都是一个字典类型的配置

        Returns:
            dict[UUID, BaseNodeData]: 验证通过后的节点数据字典，
            键为节点ID，值为节点数据对象

        Raises:
            ValidateErrorException: 当出现以下情况时抛出：
                - 节点列表为空或格式不正确
                - 节点数据类型错误
                - 节点类型无效
                - 开始节点或结束节点数量超过限制
                - 节点ID或标题重复

        """
        # 检查节点列表是否为空或格式不正确
        if not isinstance(nodes, list) or len(nodes) <= 0:
            error_msg = "工作流节点列表信息错误，请核实后重试"
            raise ValidateErrorException(error_msg)

        # 导入所有节点类型的数据类
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

        # 创建节点类型到对应数据类的映射字典
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

        # 初始化节点数据字典和计数器
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0  # 开始节点计数器
        end_nodes = 0  # 结束节点计数器

        # 遍历每个节点进行验证
        for node in nodes:
            # 检查节点数据是否为字典类型
            if not isinstance(node, dict):
                error_msg = "工作流节点数据类型出错，请核实后重试"
                raise ValidateErrorException(error_msg)

            # 获取节点类型并查找对应的数据类
            node_type = node.get("node_type", "")
            node_data_cls = node_data_classes.get(node_type)
            if not node_data_cls:
                error_msg = "工作流节点类型出错，请核实后重试"
                raise ValidateErrorException(error_msg)

            # 创建节点数据实例
            node_data = node_data_cls(**node)

            # 验证开始节点的数量限制
            if node_data.node_type == NodeType.START:
                if start_nodes >= 1:
                    error_msg = "工作流中只允许有1个开始节点"
                    raise ValidateErrorException(error_msg)
                start_nodes += 1
            # 验证结束节点的数量限制
            elif node_data.node_type == NodeType.END:
                if end_nodes >= 1:
                    error_msg = "工作流中只允许有1个结束节点"
                    raise ValidateErrorException(error_msg)
                end_nodes += 1

            # 检查节点ID是否唯一
            if node_data.id in node_data_dict:
                error_msg = "工作流节点id必须唯一，请核实后重试"
                raise ValidateErrorException(error_msg)

            # 检查节点标题是否唯一
            if any(
                item.title.strip() == node_data.title.strip()
                for item in node_data_dict.values()
            ):
                error_msg = "工作流节点title必须唯一，请核实后重试"
                raise ValidateErrorException(error_msg)

            # 将验证通过的节点添加到字典中
            node_data_dict[node_data.id] = node_data

        # 返回验证后的节点数据字典
        return node_data_dict

    @classmethod
    def _validate_edges(
        cls,
        edges: list[dict],
        node_data_dict: dict[UUID, BaseNodeData],
    ) -> dict[UUID, BaseEdgeData]:
        """验证工作流边配置的完整性和正确性。

        该方法执行以下验证：
        1. 检查边列表的基本格式和类型
        2. 验证每条边的数据结构和ID唯一性
        3. 确认边的起点和终点节点存在且类型匹配
        4. 检查是否存在重复的边连接

        Args:
            edges (list[dict]): 待验证的边列表，每个元素是一个包含边信息的字典
            node_data_dict (dict[UUID, BaseNodeData]): 已验证的节点数据字典，
                用于验证边连接的节点是否存在和类型匹配

        Returns:
            dict[UUID, BaseEdgeData]: 验证后的边数据字典，键为边的UUID，
            值为对应的BaseEdgeData对象

        Raises:
            ValidateErrorException: 当边配置不符合要求时抛出，具体错误信息包括：
                - 边列表格式错误
                - 边数据类型错误
                - 边ID重复
                - 节点不存在或类型不匹配
                - 边重复添加

        """
        # 验证边列表是否为空或格式不正确
        if not isinstance(edges, list) or len(edges) <= 0:
            error_msg = "工作流边列表信息错误，请核实后重试"
            raise ValidateErrorException(error_msg)

        # 初始化边数据字典，用于存储验证后的边数据
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        # 遍历每条边进行验证
        for edge in edges:
            # 检查边数据是否为字典类型
            if not isinstance(edge, dict):
                error_msg = "工作流边数据类型出错，请核实后重试"
                raise ValidateErrorException(error_msg)

            # 将边数据转换为BaseEdgeData对象
            edge_data = BaseEdgeData(**edge)

            # 检查边的ID是否唯一
            if edge_data.id in edge_data_dict:
                error_msg = "工作流边数据id必须唯一，请核实后重试"
                raise ValidateErrorException(error_msg)

            # 验证边的起点和终点节点是否存在且类型匹配
            if (
                edge_data.source not in node_data_dict
                or edge_data.source_type != node_data_dict[edge_data.source].node_type
                or edge_data.target not in node_data_dict
                or edge_data.target_type != node_data_dict[edge_data.target].node_type
            ):
                error_msg = "工作流边起点/终点对应的节点不存在或类型错误，请核实后重试"
                raise ValidateErrorException(error_msg)

            # 检查是否存在相同的边（起点、终点和源句柄ID都相同）
            if any(
                item.source == edge_data.source
                and item.target == edge_data.target
                and item.source_handle_id == edge_data.source_handle_id
                for item in edge_data_dict.values()
            ):
                error_msg = "工作流边数据不能重复添加"
                raise ValidateErrorException(error_msg)

            # 将验证通过的边数据添加到字典中
            edge_data_dict[edge_data.id] = edge_data

        # 返回所有验证通过的边数据
        return edge_data_dict

    @classmethod
    def _validate_graph_structure(
        cls,
        node_data_dict: dict[UUID, BaseNodeData],
        edge_data_dict: dict[UUID, BaseEdgeData],
    ) -> None:
        """验证工作流图结构的完整性和正确性。

        该方法执行以下验证：
        1. 验证图中存在且仅存在一个开始节点和一个结束节点
        2. 验证图的连通性，确保从开始节点可以到达所有其他节点
        3. 检查图中是否存在环路
        4. 验证节点的输入引用是否有效

        Args:
            node_data_dict (dict[UUID, BaseNodeData]): 节点ID到节点数据的映射字典
            edge_data_dict (dict[UUID, BaseEdgeData]): 边ID到边数据的映射字典

        Raises:
            ValidateErrorException: 当图结构不满足以下任一条件时抛出：
                - 开始节点或结束节点数量不为1
                - 开始节点或结束节点类型不正确
                - 图不连通，存在不可到达的节点
                - 图中存在环路
                - 节点的输入引用无效

        """
        # 构建邻接表和反向邻接表，用于图的遍历和验证
        adj_list = cls._build_adj_list(edge_data_dict.values())
        reverse_adj_list = cls._build_reverse_adj_list(edge_data_dict.values())
        # 计算每个节点的入度和出度
        in_degree, out_degree = cls._build_degrees(edge_data_dict.values())

        # 找出所有入度为0的节点（可能的起点）
        start_nodes = [
            node_data
            for node_data in node_data_dict.values()
            if in_degree[node_data.id] == 0
        ]
        # 找出所有出度为0的节点（可能的终点）
        end_nodes = [
            node_data
            for node_data in node_data_dict.values()
            if out_degree[node_data.id] == 0
        ]

        # 验证起点和终点的唯一性和类型正确性
        if (
            len(start_nodes) != 1
            or len(end_nodes) != 1
            or start_nodes[0].node_type != NodeType.START
            or end_nodes[0].node_type != NodeType.END
        ):
            error_msg = "工作流中有且只有一个开始/结束节点作为图结构的起点和终点"
            raise ValidateErrorException(error_msg)

        # 获取唯一的开始节点数据
        start_node_data = start_nodes[0]

        # 验证图的连通性：从开始节点出发，检查是否能到达所有其他节点
        if not cls._is_connected(adj_list, start_node_data.id):
            error_msg = "工作流中存在不可到达节点，图不联通，请核实后重试"
            raise ValidateErrorException(error_msg)

        # 检查图中是否存在环路
        if cls._is_cycle(node_data_dict.values(), adj_list, in_degree):
            error_msg = "工作流中存在环路，请核实后重试"
            raise ValidateErrorException(error_msg)

        # 验证节点的输入引用是否有效
        cls._validate_inputs_ref(node_data_dict, reverse_adj_list)

    @classmethod
    @model_validator(mode="before")
    def validate_workflow_config(cls, values: dict[str, Any]) -> dict[str, Any]:
        """验证工作流配置的完整性和正确性。

        Args:
            values: 包含工作流配置信息的字典，包括基本信息、节点列表和边列表

        Returns:
            dict[str, Any]: 验证并处理后的配置信息字典

        Raises:
            ValidateErrorException: 当配置验证失败时抛出异常

        """
        # 验证工作流的基本信息（名称、描述等）
        cls._validate_basic_info(values)

        # 获取节点和边的列表，如果不存在则使用空列表
        nodes = values.get("nodes", [])
        edges = values.get("edges", [])

        # 验证并处理节点配置，返回节点数据字典
        node_data_dict = cls._validate_nodes(nodes)
        # 验证并处理边配置，需要传入节点数据字典进行关联验证
        edge_data_dict = cls._validate_edges(edges, node_data_dict)

        # 验证整个图结构的正确性（如连通性、循环等）
        cls._validate_graph_structure(node_data_dict, edge_data_dict)

        # 将验证后的节点和边数据转换回列表形式
        values["nodes"] = list(node_data_dict.values())
        values["edges"] = list(edge_data_dict.values())

        # 返回验证并处理后的完整配置信息
        return values


class WorkflowState(TypedDict):
    """工作流状态类，用于存储工作流执行过程中的状态信息。

    Attributes:
        inputs: 工作流的输入参数字典，使用_process_dict函数处理合并
        outputs: 工作流的输出结果字典，使用_process_dict函数处理合并
        node_results: 节点执行结果的列表，使用_process_node_results函数处理合并

    """

    inputs: Annotated[dict[str, Any], _process_dict]
    outputs: Annotated[dict[str, Any], _process_dict]
    node_results: Annotated[list[NodeResult], _process_node_results]
    is_node: Annotated[bool, "是否是单个节点执行"]
