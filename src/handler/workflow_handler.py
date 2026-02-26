from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from flask import request
from flask_login import current_user, login_required
from injector import inject

from pkg.paginator.paginator import PageModel
from pkg.response.response import (
    Response,
    compact_generate_response,
    success_json,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.lib.helper import make_serializable
from src.router.redprint import route
from src.schemas.workflow_schema import (
    CreateWorkflowReq,
    GetWorkflowResp,
    GetWorkflowsWithPageReq,
    GetWorkflowsWithPageResp,
    UpdateWorkflowReq,
)
from src.service.workflow_service import WorkflowService


@inject
@dataclass
class WorkflowHandler:
    workflow_service: WorkflowService

    @route("/create", methods=["POST"])
    @swag_from(get_swagger_path("workflow_handler/create_workflow.yaml"))
    @login_required
    def create_workflow(self) -> Response:
        """创建新的工作流

        接收POST请求，创建新的工作流实例。
        需要用户登录才能访问此接口。

        Returns:
            Response: 包含新建工作流ID的成功响应，或验证失败的错误响应

        """
        # 创建工作流请求对象，用于验证请求数据
        req = CreateWorkflowReq()
        # 验证请求数据是否符合要求
        if not req.validate():
            # 如果验证失败，返回验证错误信息
            return validate_error_json(req.errors)

        # 调用服务层创建工作流，传入请求对象和当前用户信息
        workflow = self.workflow_service.create_workflow(req, current_user)

        # 返回成功响应，包含新建工作流的ID
        return success_json({"id": workflow.id})

    @route("/<uuid:workflow_id>/delete", methods=["POST"])
    @swag_from(get_swagger_path("workflow_handler/delete_workflow.yaml"))
    @login_required
    def delete_workflow(self, workflow_id: UUID) -> Response:
        """删除指定的工作流

        Args:
            workflow_id (UUID): 要删除的工作流的唯一标识符

        Returns:
            Response: 包含成功消息的响应对象

        Note:
            需要用户登录才能执行此操作
            只有工作流的创建者才有权限删除该工作流

        """
        self.workflow_service.delete_workflow(workflow_id, current_user)

        return success_message_json("删除工作流成功")

    @route("/<uuid:workflow_id>/update", methods=["POST"])
    @swag_from(get_swagger_path("workflow_handler/update_workflow.yaml"))
    @login_required
    def update_workflow(self, workflow_id: UUID) -> Response:
        """更新工作流信息

        Args:
            workflow_id (UUID): 要更新的工作流的唯一标识符

        Returns:
            Response: 包含操作结果的响应对象
                - 成功时返回成功消息和状态码
                - 验证失败时返回错误信息

        Raises:
            ValidationError: 当请求数据验证失败时

        """
        req = UpdateWorkflowReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.workflow_service.update_workflow(workflow_id, current_user, **req.data)

        return success_message_json("更新工作流成功")

    @route("/<uuid:workflow_id>", methods=["GET"])
    @swag_from(get_swagger_path("workflow_handler/get_workflow.yaml"))
    @login_required
    def get_workflow(self, workflow_id: UUID) -> Response:
        """获取单个工作流信息

        根据工作流ID获取指定工作流的详细信息。

        Args:
            workflow_id (UUID): 要获取的工作流的唯一标识符

        Returns:
            Response: 包含工作流详细信息的响应对象

        """
        workflow = self.workflow_service.get_workflow(workflow_id, current_user)

        resp = GetWorkflowResp()

        return success_json(resp.dump(workflow))

    @route("", methods=["GET"])
    @swag_from(get_swagger_path("workflow_handler/get_workflows_with_page.yaml"))
    @login_required
    def get_workflows_with_page(self) -> Response:
        """分页获取工作流列表

        通过分页参数获取当前用户的工作流列表，支持按条件筛选和排序。

        Returns:
            Response: 包含分页工作流列表的响应对象

        """
        req = GetWorkflowsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        workflows, paginator = self.workflow_service.get_workflows_with_page(
            req,
            current_user,
        )

        resp = GetWorkflowsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(workflows), paginator=paginator))

    @route("/<uuid:workflow_id>/draft/update", methods=["POST"])
    @swag_from(get_swagger_path("workflow_handler/update_draft_graph.yaml"))
    @login_required
    def update_draft_graph(self, workflow_id: UUID) -> Response:
        """更新工作流草稿图

        Args:
            workflow_id (UUID): 工作流ID

        Returns:
            Response: 更新成功的响应消息

        """
        # 获取请求体中的草稿图数据，如果没有则使用空的节点和边
        draft_graph_dict = request.get_json(force=True, silent=True) or {
            "nodes": [],
            "edges": [],
        }

        # 调用服务层更新工作流草稿图
        self.workflow_service.update_draft_graph(
            workflow_id,
            draft_graph_dict,
            current_user,
        )

        # 返回更新成功的响应
        return success_message_json("更新工作流草稿成功")

    @route("/<uuid:workflow_id>/draft", methods=["GET"])
    @swag_from(get_swagger_path("workflow_handler/get_draft_graph.yaml"))
    @login_required
    def get_draft_graph(self, workflow_id: UUID) -> Response:
        """获取指定工作流的草稿图数据

        Args:
            workflow_id (UUID): 工作流的唯一标识符

        Returns:
            Response: 包含草稿图数据的成功响应
                - nodes: 节点列表
                - edges: 边列表

        """
        # 调用服务层获取工作流的草稿图数据
        draft_graph = self.workflow_service.get_draft_graph(workflow_id, current_user)

        # 返回包含草稿图数据的成功响应
        serialized_graph = make_serializable(draft_graph)
        return success_json(serialized_graph)

    @route("/<uuid:workflow_id>/debug", methods=["POST"])
    @swag_from(get_swagger_path("workflow_handler/debug_workflow.yaml"))
    @login_required
    def debug_workflow(self, workflow_id: UUID) -> Response:
        """调试指定的工作流

        Args:
            workflow_id (UUID): 要调试的工作流ID

        Returns:
            Response: 包含调试结果的响应对象

        """
        # 从请求体中获取输入参数，如果没有则使用空字典
        request_data = request.get_json(force=True, silent=True) or {}
        inputs = request_data.get("inputs", {})
        node_id = request_data.get("node_id")

        # 调用服务层执行工作流调试
        response = self.workflow_service.debug_workflow(
            workflow_id,
            inputs,
            current_user,
            node_id,
        )

        # 返回调试结果的响应
        return compact_generate_response(response)

    @route("/<uuid:workflow_id>/publish", methods=["POST"])
    @swag_from(get_swagger_path("workflow_handler/publish_workflow.yaml"))
    @login_required
    def publish_workflow(self, workflow_id: UUID) -> Response:
        self.workflow_service.publish_workflow(workflow_id, current_user)

        return success_message_json("工作流发布成功")

    @route("/<uuid:workflow_id>/unpublish", methods=["POST"])
    @swag_from(get_swagger_path("workflow_handler/cancel_publish_workflow.yaml"))
    @login_required
    def cancel_publish_workflow(self, workflow_id: UUID) -> Response:
        self.workflow_service.cancel_workflow(workflow_id, current_user)

        return success_message_json("取消工作流发布成功")
