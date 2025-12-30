from dataclasses import dataclass
from uuid import UUID

from injector import inject

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.entity.workflow_entity import DEFAULT_WORKFLOW_CONFIG, WorkflowStatus
from src.exception.exception import (
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from src.model.account import Account
from src.model.workflow import Workflow
from src.schemas.workflow_schema import CreateWorkflowReq, GetWorkflowsWithPageReq
from src.service.base_service import BaseService


@inject
@dataclass
class WorkflowService(BaseService):
    db: SQLAlchemy

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
