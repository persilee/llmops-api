import json
import logging
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from venv import logger

from flask import request
from injector import inject

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.tools.builtin_tools.providers.builtin_provider_manager import (
    BuiltinProviderManager,
)
from src.core.workflow import Workflow as WorkflowTool
from src.core.workflow.entities.edge_entity import BaseEdgeData
from src.core.workflow.entities.node_entity import BaseNodeData, NodeStatus, NodeType
from src.core.workflow.entities.variable_entity import VariableEntity
from src.core.workflow.entities.workflow_entity import WorkflowConfig
from src.core.workflow.nodes.code.code_entity import CodeNodeData
from src.core.workflow.nodes.dataset_retrieval.dataset_retrieval_entity import (
    DatasetRetrievalNodeData,
)
from src.core.workflow.nodes.end.end_entity import EndNodeData
from src.core.workflow.nodes.http_request.http_request_entity import HttpRequestNodeData
from src.core.workflow.nodes.llm.llm_entity import LLMNodeData
from src.core.workflow.nodes.start.start_entity import StartNodeData
from src.core.workflow.nodes.template_transform.template_transform_entity import (
    TemplateTransformNodeData,
)
from src.core.workflow.nodes.tool.tool_entity import ToolNodeData
from src.entity.workflow_entity import (
    DEFAULT_DRAFT_GRAPH,
    DEFAULT_WORKFLOW_CONFIG,
    WorkflowStatus,
)
from src.exception.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from src.lib.helper import convert_model_to_dict, make_serializable
from src.model.account import Account
from src.model.api_tool import ApiTool
from src.model.dataset import Dataset
from src.model.workflow import Workflow, WorkflowResult
from src.schemas.workflow_schema import CreateWorkflowReq, GetWorkflowsWithPageReq
from src.service.base_service import BaseService


@inject
@dataclass
class WorkflowService(BaseService):
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    logger = logging.getLogger(__name__)

    def publish_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """发布工作流。

        Args:
            workflow_id (UUID): 要发布的工作流ID
            account (Account): 执行发布操作的账户对象

        Returns:
            Workflow: 发布成功的工作流对象

        Raises:
            FailException: 当工作流未通过调试时抛出
            ValidateErrorException: 当工作流配置验证失败时抛出

        """
        # 获取指定ID的工作流，同时验证用户权限
        workflow = self.get_workflow(workflow_id, account)

        try:
            # 尝试创建工作流配置对象，包含账户ID、名称、描述和图结构信息
            WorkflowConfig(
                account_id=account.id,
                name=workflow.tool_call_name,
                description=workflow.description,
                nodes=workflow.draft_graph.get("nodes", []),
                edges=workflow.draft_graph.get("edges", []),
            )
        except Exception as e:
            # 如果创建配置失败，更新工作流的调试状态为未通过
            self.update(workflow, is_debug_passed=False)
            error_msg = "工作流发布失败"
            # 抛出验证错误异常，并保留原始异常信息
            raise ValidateErrorException(error_msg) from e

        # 更新工作流状态为已发布，并设置调试状态为未通过
        self.update(
            workflow,
            graph=workflow.draft_graph,
            status=WorkflowStatus.PUBLISHED,
            is_debug_passed=False,
            published_at=datetime.now(UTC),
        )

        # 返回工作流对象
        return workflow

    def cancel_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """取消已发布的工作流

        Args:
            workflow_id: 工作流ID
            account: 账户信息

        Returns:
            Workflow: 更新后的工作流对象

        Raises:
            FailException: 当工作流未发布时抛出异常

        """
        # 获取工作流并验证权限
        workflow = self.get_workflow(workflow_id, account)
        # 检查工作流是否已发布
        if workflow.status != WorkflowStatus.PUBLISHED:
            error_msg = "工作流未发布"
            raise FailException(error_msg)

        # 更新工作流状态：清空图结构、设置为草稿状态、重置调试状态
        self.update(
            workflow,
            graph={},
            status=WorkflowStatus.DRAFT,
            is_debug_passed=False,
        )

        return workflow

    def debug_workflow(
        self,
        workflow_id: UUID,
        inputs: dict[str, Any],
        account: Account,
    ) -> Generator:
        """调试工作流执行

        Args:
            workflow_id: 工作流ID
            inputs: 输入参数字典
            account: 账户信息

        Returns:
            Generator: 流式返回工作流执行结果

        """
        # 1.根据传递的id获取工作流并校验权限
        workflow = self.get_workflow(workflow_id, account)

        # 2.创建工作流工具实例，配置包含账户ID、名称、描述和图结构
        workflow_tool = WorkflowTool(
            workflow_config=WorkflowConfig(
                account_id=account.id,
                name=workflow.tool_call_name,
                description=workflow.description,
                nodes=workflow.draft_graph.get("nodes", []),
                edges=workflow.draft_graph.get("edges", []),
            ),
        )

        def handle_stream() -> Generator:
            """处理工作流执行的流式输出

            Returns:
                Generator: 流式返回工作流执行过程中的节点结果

            """
            # 3.定义变量存储所有节点运行结果
            node_results = []

            # 4.创建工作流运行结果记录，包含初始状态和运行时信息
            workflow_result = self.create(
                WorkflowResult,
                app_id=None,
                account_id=account.id,
                workflow_id=workflow.id,
                graph=workflow.draft_graph,
                state=[],
                latency=0,
                status=NodeStatus.RUNNING,
            )

            # 5.开始执行工作流并记录执行时间
            start_at = time.perf_counter()
            try:
                # 5.1 流式获取工作流执行结果
                for chunk in workflow_tool.stream(inputs):
                    # 5.2 chunk格式为:{"node_name": WorkflowState}，取出第一个节点名称
                    first_key = next(iter(chunk))

                    # 5.3 处理节点运行结果
                    # 5.3.1 跳过虚拟节点（无实际执行结果的节点）
                    if len(chunk[first_key]["node_results"]) == 0:
                        continue
                    # 5.3.2 获取并转换节点结果为字典格式
                    node_result = chunk[first_key]["node_results"][0]
                    node_result_dict = convert_model_to_dict(node_result)
                    node_results.append(node_result_dict)

                    # 5.4 组装响应数据并流式输出
                    data = {
                        "id": str(uuid.uuid4()),
                        **node_result_dict,
                    }
                    yield f"event: workflow\ndata: {json.dumps(data)}\n\n"

                # 工作流执行成功，更新结果状态和调试状态
                self.update(
                    workflow_result,
                    status=NodeStatus.SUCCEEDED,
                    state=node_results,
                    latency=(time.perf_counter() - start_at),
                )

            except (ValidateErrorException, ValueError, RuntimeError) as e:
                # 7.处理执行过程中的异常，记录错误日志并更新失败状态
                logger.exception(
                    "执行工作流发生错误, workflow_id: %s error: %s",
                    workflow_id,
                    e,
                )
                # 7.1 更新工作流结果为失败状态
                self.update(
                    workflow_result,
                    status=NodeStatus.FAILED,
                    state=node_results,
                    latency=(time.perf_counter() - start_at),
                )

        result = handle_stream()
        # 标记工作流调试通过
        self.update(
            workflow,
            is_debug_passed=True,
        )

        return result

    def get_draft_graph(self, workflow_id: UUID, account: Account) -> dict:
        """获取工作流的草稿图数据。

        该方法会执行以下操作：
        1. 验证用户权限并获取工作流
        2. 验证草稿图结构的合法性
        3. 为不同类型的节点附加相应的元数据：
           - 工具节点：附加工具的名称、图标、参数等信息
           - 知识库检索节点：附加知识库的名称、图标等信息
           - 迭代节点：附加工作流的名称、图标等信息

        Args:
            workflow_id (UUID): 工作流的唯一标识符
            account (Account): 当前操作的用户账户对象

        Returns:
            dict: 包含验证后的草稿图数据的字典，包括节点和边的完整信息，
                 以及各类节点的元数据信息

        Raises:
            ForbiddenException: 当用户没有权限访问该工作流时
            NotFoundException: 当工作流不存在时
            ValidateErrorException: 当草稿图结构不合法时

        """
        # 1.根据传递的id获取工作流并校验权限
        workflow = self.get_workflow(workflow_id, account)

        # 2.提取草稿图结构信息并校验(不更新校验后的数据到数据库)
        draft_graph = workflow.draft_graph
        validate_draft_graph = self._validate_graph(workflow_id, draft_graph, account)

        # 3.循环遍历节点信息，为工具节点/知识库节点附加元数据
        for node in validate_draft_graph["nodes"]:
            if node.get("node_type") == NodeType.TOOL:
                # 4.判断工具的类型执行不同的操作
                if node.get("type") == "builtin_tool":
                    # 5.节点类型为工具，则附加工具的名称、图标、参数等额外信息
                    provider = self.builtin_provider_manager.get_provider(
                        node.get("provider_id"),
                    )
                    if not provider:
                        continue

                    # 6.获取提供者下的工具实体，并检测是否存在
                    tool_entity = provider.get_tool_entity(node.get("tool_id"))
                    if not tool_entity:
                        continue

                    # 7.判断工具的params和草稿中的params是否一致，
                    # 如果不一致则全部重置为默认值（或者考虑删除这个工具的引用）
                    param_keys = {param.name for param in tool_entity.params}
                    params = node.get("params")
                    if set(params.keys()) - param_keys:
                        params = {
                            param.name: param.default
                            for param in tool_entity.params
                            if param.default is not None
                        }

                    # 8.数据校验成功附加展示信息
                    provider_entity = provider.provider_entity
                    node["meta"] = {
                        "type": "builtin_tool",
                        "provider": {
                            "id": provider_entity.name,
                            "name": provider_entity.name,
                            "label": provider_entity.label,
                            "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                            "description": provider_entity.description,
                        },
                        "tool": {
                            "id": tool_entity.name,
                            "name": tool_entity.name,
                            "label": tool_entity.label,
                            "description": tool_entity.description,
                            "params": params,
                        },
                    }
                elif node.get("type") == "api_tool":
                    # 9.查询数据库获取对应的工具记录，并检测是否存在
                    tool_record = (
                        self.db.session.query(ApiTool)
                        .filter(
                            ApiTool.provider_id == node.get("provider_id"),
                            ApiTool.name == node.get("tool_id"),
                            ApiTool.account_id == account.id,
                        )
                        .one_or_none()
                    )
                    if not tool_record:
                        continue

                    # 10.组装api工具展示信息
                    provider = tool_record.provider
                    node["meta"] = {
                        "type": "api_tool",
                        "provider": {
                            "id": str(provider.id),
                            "name": provider.name,
                            "label": provider.name,
                            "icon": provider.icon,
                            "description": provider.description,
                        },
                        "tool": {
                            "id": str(tool_record.id),
                            "name": tool_record.name,
                            "label": tool_record.name,
                            "description": tool_record.description,
                            "params": {},
                        },
                    }
                else:
                    # 11.处理未知类型的工具节点，设置空的元数据结构
                    node["meta"] = {
                        "type": "api_tool",
                        "provider": {
                            "id": "",
                            "name": "",
                            "label": "",
                            "icon": "",
                            "description": "",
                        },
                        "tool": {
                            "id": "",
                            "name": "",
                            "label": "",
                            "description": "",
                            "params": {},
                        },
                    }
            elif node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                # 12.节点类型为知识库检索，需要附加知识库的名称、图标等信息
                datasets = (
                    self.db.session.query(Dataset)
                    .filter(
                        Dataset.id.in_(node.get("dataset_ids", [])),
                        Dataset.account_id == account.id,
                    )
                    .all()
                )
                # 13.限制最多显示5个知识库
                datasets = datasets[:5]
                node["dataset_ids"] = [str(dataset.id) for dataset in datasets]
                node["meta"] = {
                    "datasets": [
                        {
                            "id": dataset.id,
                            "name": dataset.name,
                            "icon": dataset.icon,
                            "description": dataset.description,
                        }
                        for dataset in datasets
                    ],
                }
            elif node.get("node_type") == NodeType.ITERATION:
                # 14.节点类型为迭代节点，需要附加工作流的名称、图标等信息
                workflows = (
                    self.db.session.query(Workflow)
                    .filter(
                        Workflow.id.in_(node.get("workflow_ids", [])),
                        Workflow.account_id == account.id,
                        Workflow.status == WorkflowStatus.PUBLISHED,
                    )
                    .all()
                )
                # 15.限制最多显示1个工作流
                workflows = workflows[:1]
                node["workflow_ids"] = [str(workflow.id) for workflow in workflows]
                node["meta"] = {
                    "workflows": [
                        {
                            "id": workflow.id,
                            "name": workflow.name,
                            "icon": workflow.icon,
                            "description": workflow.description,
                        }
                        for workflow in workflows
                    ],
                }

        # 16.返回验证后的草稿图数据
        return validate_draft_graph

    def create_workflow(self, req: CreateWorkflowReq, account: Account) -> Workflow:
        """创建新的工作流。

        Args:
            req (CreateWorkflowReq): 创建工作流的请求参数，包含工作流的基本信息
            account (Account): 创建工作流的账户信息

        Returns:
            Workflow: 新创建的工作流实例

        Raises:
            ValidateErrorException: 当已存在同名工作流时抛出

        """
        # 查询数据库中是否已存在相同名称的工作流
        check_workflow = (
            self.db.session.query(Workflow)
            .filter(
                Workflow.tool_call_name
                == req.tool_call_name.data.strip(),  # 匹配工作流名称
                Workflow.account_id == account.id,  # 匹配账户ID
            )
            .one_or_none()  # 返回最多一个结果，如果没有则返回None
        )

        # 如果已存在同名工作流，抛出验证错误
        if check_workflow:
            error_msg = f"工作流名称 {req.tool_call_name.data.strip()} 已存在"
            raise ValidateErrorException(error_msg)

        # 创建新的工作流，合并请求参数、默认配置和其他必要字段
        return self.create(
            Workflow,
            **{
                **req.data,  # 请求参数中的数据
                **DEFAULT_WORKFLOW_CONFIG,  # 默认工作流配置
                "account_id": account.id,  # 关联的账户ID
                "is_debug_passed": False,  # 初始调试状态为未通过
                "status": WorkflowStatus.DRAFT,  # 初始状态为草稿
                "tool_call_name": req.tool_call_name.data.strip(),  # 工作流名称
                "draft_graph": DEFAULT_DRAFT_GRAPH,  # 草稿图配置
            },
        )

    def delete_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """删除指定的工作流

        Args:
            workflow_id (UUID): 要删除的工作流ID
            account (Account): 执行删除操作的账户信息

        Returns:
            Workflow: 被删除的工作流对象

        """
        workflow = self.get_workflow(workflow_id, account)

        self.delete(workflow)

        return workflow

    def update_workflow(
        self,
        workflow_id: UUID,
        account: Account,
        **kwargs: dict,
    ) -> Workflow:
        """更新工作流信息。

        Args:
            workflow_id (UUID): 要更新的工作流ID
            account (Account): 执行更新的账户信息
            **kwargs: 要更新的工作流字段，如tool_call_name等

        Returns:
            Workflow: 更新后的工作流对象

        Raises:
            ValidateErrorException: 当工作流名称已存在时抛出
            NotFoundException: 当工作流不存在时抛出
            ForbiddenException: 当没有权限访问时抛出

        """
        # 获取要更新的工作流
        workflow = self.get_workflow(workflow_id, account)

        # 检查是否存在同名的工作流
        check_workflow = (
            self.db.session.query(Workflow)
            .filter(
                Workflow.tool_call_name == kwargs.get("tool_call_name", "").strip(),
                Workflow.account_id == account.id,
                Workflow.id != workflow.id,
            )
            .one_or_none()
        )
        # 如果存在同名工作流，抛出验证错误
        if check_workflow:
            error_msg = "工作流名称已存在"
            raise ValidateErrorException(error_msg)

        # 更新工作流
        self.update(workflow, **kwargs)

        # 返回更新后的工作流
        return workflow

    def get_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """根据ID获取工作流并验证权限

        Args:
            workflow_id (UUID): 工作流ID
            account (Account): 账户信息

        Returns:
            Workflow: 返回获取到的工作流对象

        Raises:
            NotFoundException: 当工作流不存在时抛出
            ForbiddenException: 当用户无权限访问该工作流时抛出

        """
        # 根据ID获取工作流
        workflow = self.get(Workflow, workflow_id)

        # 检查工作流是否存在
        if not workflow:
            error_msg = "工作流不存在"
            raise NotFoundException(error_msg)

        # 验证用户是否有权限访问该工作流
        if workflow.account_id != account.id:
            error_msg = "无权限删除该工作流"
            raise ForbiddenException(error_msg)

        # 返回获取到的工作流
        return workflow

    def get_workflows_with_page(
        self,
        req: GetWorkflowsWithPageReq,
        account: Account,
    ) -> tuple[list[Workflow], Paginator]:
        """分页获取工作流列表。

        Args:
            req (GetWorkflowsWithPageReq): 分页查询请求参数，包含分页信息、\
                搜索关键词和状态过滤条件
            account (Account): 当前账户信息

        Returns:
            tuple[list[Workflow], Paginator]: 返回一个元组，包含工作流列表和分页器对象
                - list[Workflow]: 符合条件的工作流列表
                - Paginator: 分页器对象，包含分页相关信息

        """
        # 创建分页器对象，用于处理分页相关逻辑
        paginator = Paginator(db=self.db, req=req)

        # 初始化过滤条件列表，默认只查询当前账户的工作流
        filters = [Workflow.account_id == account.id]
        # 如果存在搜索关键词，添加名称模糊匹配的过滤条件
        if req.search_word.data:
            filters.append(Workflow.name.ilike(f"%{req.search_word.data}%"))
        # 如果指定了状态，添加状态过滤条件
        if req.status.data:
            filters.append(Workflow.status == req.status.data)

        # 执行分页查询
        # 1. 创建工作流查询对象
        # 2. 应用所有过滤条件
        # 3. 按创建时间降序排序
        # 4. 执行分页
        workflows = paginator.paginate(
            self.db.session.query(Workflow)
            .filter(*filters)
            .order_by(Workflow.created_at.desc()),
        )

        # 返回分页结果和分页器对象
        return workflows, paginator

    def update_draft_graph(
        self,
        workflow_id: UUID,
        draft_graph: dict[str, Any],
        account: Account,
    ) -> Workflow:
        """更新工作流的草稿图。

        Args:
            workflow_id (UUID): 工作流ID
            draft_graph (dict[str, Any]): 草稿图数据，包含节点和边的配置信息
            account (Account): 执行操作的账户对象

        Returns:
            Workflow: 更新后的工作流对象

        Raises:
            ValidateErrorException: 当草稿图验证失败时抛出
            ForbiddenException: 当用户没有权限访问该工作流时抛出
            NotFoundException: 当指定的工作流不存在时抛出

        """
        # 获取指定ID的工作流，确保用户有权限访问
        workflow = self.get_workflow(workflow_id, account)

        # 验证草稿图的合法性，包括节点和边的有效性
        validate_draft_graph = self._validate_graph(workflow_id, draft_graph, account)

        # 更新工作流的草稿图，并将调试状态重置为未通过
        serializable_graph = make_serializable(validate_draft_graph)
        self.update(
            workflow,
            draft_graph=serializable_graph,
            is_debug_passed=False,
            updated_at=datetime.now(UTC),
        )

        # 返回更新后的工作流对象
        return workflow

    def _raise_validation_error(self, error_msg: str) -> None:
        """抛出验证错误的内部函数。

        Args:
            error_msg (str): 错误消息

        Raises:
            ValidateErrorException: 验证错误异常

        """
        raise ValidateErrorException(error_msg)

    def _validate_graph(
        self,
        workflow_id: UUID,
        graph: dict[str, Any],
        account: Account,
    ) -> dict[str, Any]:
        """验证工作流图的结构和内容

        Args:
            workflow_id: 工作流ID
            graph: 待验证的工作流图，包含节点和边
            account: 当前操作账户

        Returns:
            dict: 验证后的工作流图，包含验证通过的节点和边

        """
        # 从图中获取节点和边列表
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # 初始化节点类型与对应数据类的映射字典
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

        # 初始化节点数据字典和特殊节点计数器
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0  # 开始节点计数
        end_nodes = 0  # 结束节点计数

        # 遍历并验证每个节点
        for node in nodes:
            try:
                # 验证节点的基本信息和数据结构
                node_data = self._validate_node(node, node_data_classes, node_data_dict)
                # 验证特殊节点（开始节点和结束节点）的唯一性
                node_data, start_nodes, end_nodes = self._validate_special_node(
                    node_data,
                    account,
                    workflow_id,
                    start_nodes,
                    end_nodes,
                )
                # 将验证通过的节点数据存入字典
                node_data_dict[node_data.id] = node_data
            except (ValueError, ValidateErrorException) as e:
                if node.get("node_type") == NodeType.END:
                    # 获取结束节点的输出配置
                    outputs = node.get("outputs", [])
                    # 遍历输出配置，找出无效的输出
                    valid_outputs = []
                    for output in outputs:
                        try:
                            # 验证每个输出项
                            VariableEntity(**output)
                            valid_outputs.append(output)
                        except (ValueError, ValidateErrorException) as output_error:
                            error_msg = (
                                f"结束节点输出验证失败: {output}, error: {output_error}"
                            )
                            logger.warning(error_msg)
                            continue

                    # 更新节点的输出配置，只保留有效的输出
                    node["outputs"] = valid_outputs
                    node_data = self._validate_node(
                        node,
                        node_data_classes,
                        node_data_dict,
                    )
                    node_data_dict[node_data.id] = node_data

                # 如果节点验证失败，跳过该节点
                logger.warning(f"节点验证失败: {node}, error: {e}")
                continue

        # 初始化边数据字典
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        # 遍历并验证每条边
        for edge in edges:
            try:
                # 验证边的基本信息和数据结构
                edge_data = self._validate_edge(edge, edge_data_dict, node_data_dict)
                # 将验证通过的边数据存入字典
                edge_data_dict[edge_data.id] = edge_data
            except (ValueError, ValidateErrorException):
                # 如果边验证失败，跳过该边
                logger.warning(f"边 {edge} 验证失败，跳过该边")
                continue

        # 构建并返回验证后的工作流图
        return {
            "nodes": [
                # 将节点数据对象转换为字典格式
                convert_model_to_dict(node_data)
                for node_data in node_data_dict.values()
            ],
            "edges": [
                # 将边数据对象转换为字典格式
                convert_model_to_dict(edge_data)
                for edge_data in edge_data_dict.values()
            ],
        }

    def _validate_node(
        self,
        node: dict,
        node_data_classes: dict,
        node_data_dict: dict,
    ) -> BaseNodeData:
        """验证工作流节点数据的有效性。

        Args:
            node (dict): 待验证的节点数据，包含节点类型、ID、标题等信息
            node_data_classes (dict): 节点类型与对应数据类的映射字典，\
                用于创建节点数据对象
            node_data_dict (dict): 已验证的节点数据字典，用于检查节点ID和标题的唯一性

        Returns:
            BaseNodeData: 验证通过的节点数据对象

        Raises:
            ValidateErrorException: 当节点数据类型错误、节点类型无效、\
                节点ID或标题重复时抛出

        """
        # 验证节点数据是否为字典类型
        if not isinstance(node, dict):
            self._raise_validation_error("工作流节点数据类型出错，请核实后重试")

        # 获取节点类型并查找对应的数据类
        node_type = node.get("node_type", "")
        node_data_cls = node_data_classes.get(node_type)
        # 检查节点类型是否有效
        if node_data_cls is None:
            self._raise_validation_error("工作流节点类型出错，请核实后重试")

        # 使用节点数据类创建节点数据对象
        node_data = node_data_cls(**node)

        # 验证节点ID是否已存在
        if node_data.id in node_data_dict:
            self._raise_validation_error("工作流节点id必须唯一，请核实后重试")

        # 验证节点标题是否唯一（去除前后空格后比较）
        if any(
            item.title.strip() == node_data.title.strip()
            for item in node_data_dict.values()
        ):
            self._raise_validation_error("工作流节点title必须唯一，请核实后重试")

        # 返回验证通过的节点数据对象
        return node_data

    def _validate_special_node(
        self,
        node_data: BaseNodeData,
        account: Account,
        workflow_id: UUID,
        start_nodes: int,
        end_nodes: int,
    ) -> tuple[BaseNodeData, int, int]:
        """验证特殊节点的有效性，包括开始节点、结束节点、数据集检索节点和迭代节点

        Args:
            node_data: 节点数据对象
            account: 账户信息
            workflow_id: 当前工作流ID
            start_nodes: 已存在的开始节点数量
            end_nodes: 已存在的结束节点数量

        Returns:
            tuple[BaseNodeData, int, int]: 返回更新后的节点数据、\
                开始节点数量和结束节点数量

        """
        # 验证开始节点：确保工作流中只有一个开始节点
        if node_data.node_type == NodeType.START:
            if start_nodes >= 1:
                self._raise_validation_error("工作流中只允许有1个开始节点")
            start_nodes += 1
        # 验证结束节点：确保工作流中只有一个结束节点
        elif node_data.node_type == NodeType.END:
            if end_nodes >= 1:
                self._raise_validation_error("工作流中只允许有1个结束节点")
            end_nodes += 1
        # 验证数据集检索节点：检查数据集是否存在且属于当前账户
        elif node_data.node_type == NodeType.DATASET_RETRIEVAL:
            datasets = (
                self.db.session.query(Dataset)
                .filter(
                    Dataset.id.in_(node_data.dataset_ids[:5]),  # 最多支持5个数据集
                    Dataset.account_id == account.id,  # 确保数据集属于当前账户
                )
                .all()
            )
            # 更新节点数据中的数据集ID列表，只保留有效的数据集ID
            node_data.dataset_ids = [dataset.id for dataset in datasets]
        # 验证迭代节点：检查子工作流是否存在且已发布
        elif node_data.node_type == NodeType.ITERATION:
            workflows = (
                self.db.session.query(Workflow)
                .filter(
                    Workflow.id.in_(node_data.workflow_ids[:1]),  # 最多支持1个子工作流
                    Workflow.account_id == account.id,  # 确保工作流属于当前账户
                    Workflow.status == WorkflowStatus.PUBLISHED,  # 确保工作流已发布
                )
                .all()
            )
            # 更新节点数据中的工作流ID列表，排除当前工作流ID
            node_data.workflow_ids = [
                workflow.id for workflow in workflows if workflow.id != workflow_id
            ]

        return node_data, start_nodes, end_nodes

    def _validate_edge(
        self,
        edge: dict,
        edge_data_dict: dict,
        node_data_dict: dict,
    ) -> BaseEdgeData:
        """验证工作流边数据的有效性

        Args:
            edge: 待验证的边数据字典
            edge_data_dict: 已存在的边数据字典，用于检查重复
            node_data_dict: 节点数据字典，用于验证边的起点和终点

        Returns:
            BaseEdgeData: 验证通过后的边数据对象

        Raises:
            ValidateErrorException: 当边数据验证失败时抛出

        """
        # 检查边数据是否为字典类型
        if not isinstance(edge, dict):
            self._raise_validation_error("工作流边数据类型出错，请核实后重试")

        # 将边数据转换为BaseEdgeData对象
        edge_data = BaseEdgeData(**edge)

        # 检查边的ID是否已存在
        if edge_data.id in edge_data_dict:
            self._raise_validation_error("工作流边数据id必须唯一，请核实后重试")

        # 验证边的起点和终点节点是否存在且类型匹配
        if (
            edge_data.source not in node_data_dict
            or edge_data.source_type != node_data_dict[edge_data.source].node_type
            or edge_data.target not in node_data_dict
            or edge_data.target_type != node_data_dict[edge_data.target].node_type
        ):
            self._raise_validation_error(
                "工作流边起点/终点对应的节点不存在或类型错误，请核实后重试",
            )

        # 检查是否已存在相同的边（起点、终点和源句柄ID都相同）
        if any(
            (
                item.source == edge_data.source
                and item.target == edge_data.target
                and item.source_handle_id == edge_data.source_handle_id
            )
            for item in edge_data_dict.values()
        ):
            self._raise_validation_error("工作流边数据不能重复添加")

        # 返回验证通过的边数据对象
        return edge_data
