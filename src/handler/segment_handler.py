from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from flask import request
from flask_login import current_user, login_required
from injector import inject

from pkg.paginator.paginator import PageModel
from pkg.response.response import (
    Response,
    success_json,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.segment_schema import (
    CreateSegmentReq,
    GetSegmentResp,
    GetSegmentsWithPageReq,
    GetSegmentsWithPageResp,
    UpdateSegmentEnabledReq,
    UpdateSegmentReq,
)
from src.service.segment_service import SegmentService


@inject
@dataclass
class SegmentHandler:
    segment_service: SegmentService

    @route(
        "/<uuid:dataset_id>/document/<uuid:document_id>/segment/<uuid:segment_id>/delete",
        methods=["POST"],
    )
    @swag_from(get_swagger_path("segment_handler/delete_segment.yaml"))
    @login_required
    def delete_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
    ) -> Response:
        """删除文档片段

        Args:
            dataset_id (UUID): 数据集ID
            document_id (UUID): 文档ID
            segment_id (UUID): 文档片段ID

        Returns:
            Response: 删除成功的响应消息

        """
        self.segment_service.delete_segment(
            dataset_id,
            document_id,
            segment_id,
            current_user,
        )

        return success_message_json("删除文档片段成功")

    @route(
        "/<uuid:dataset_id>/document/<uuid:document_id>/segment/create",
        methods=["POST"],
    )
    @swag_from(get_swagger_path("segment_handler/create_segment.yaml"))
    @login_required
    def create_segment(self, dataset_id: UUID, document_id: UUID) -> Response:
        """创建新的文档片段接口。

        该接口用于在指定文档中创建新的文本片段：
        1. 验证请求数据的合法性
        2. 调用服务层创建文档片段
        3. 返回创建结果

        Args:
            dataset_id (UUID): 数据集ID，用于标识所属知识库
            document_id (UUID): 文档ID，指定要添加片段的文档

        Returns:
            Response: HTTP响应对象，包含创建结果信息

        Raises:
            ValidationError: 当请求数据验证失败时

        Note:
            请求方法: POST
            需要在请求体中提供片段内容和关键词信息

        """
        req = CreateSegmentReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.segment_service.create_segment(dataset_id, document_id, req, current_user)

        return success_message_json("创建文档片段成功")

    @route("/<uuid:dataset_id>/documents/<uuid:document_id>/segments", methods=["GET"])
    @swag_from(get_swagger_path("segment_handler/get_segments_with_page.yaml"))
    @login_required
    def get_segments_with_page(self, dataset_id: UUID, document_id: UUID) -> Response:
        """分页获取文档片段列表接口。

        该接口用于获取指定文档中的片段列表：
        1. 验证分页请求参数
        2. 调用服务层查询片段列表
        3. 返回分页结果

        Args:
            dataset_id (UUID): 数据集ID，用于标识所属知识库
            document_id (UUID): 文档ID，指定要查询的文档

        Returns:
            Response: HTTP响应对象，包含分页的片段列表信息

        Raises:
            ValidationError: 当分页参数验证失败时

        Note:
            请求方法: GET
            支持通过查询参数进行分页和搜索

        """
        req = GetSegmentsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        segments, paginator = self.segment_service.get_segment_with_page(
            dataset_id,
            document_id,
            req,
            current_user,
        )

        resp = GetSegmentsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(segments), paginator=paginator))

    @route(
        "/<uuid:dataset_id>/document/<uuid:document_id>/segment/<uuid:segment_id>",
        methods=["GET"],
    )
    @swag_from(get_swagger_path("segment_handler/get_segment.yaml"))
    @login_required
    def get_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
    ) -> Response:
        """获取单个文档片段详情接口。

        该接口用于获取指定文档片段的详细信息：
        1. 验证参数合法性
        2. 调用服务层查询片段信息
        3. 返回片段详情

        Args:
            dataset_id (UUID): 数据集ID，用于标识所属知识库
            document_id (UUID): 文档ID，验证片段所属文档
            segment_id (UUID): 片段ID，指定要查询的片段

        Returns:
            Response: HTTP响应对象，包含片段的详细信息

        Note:
            请求方法: GET
            返回指定ID的片段完整信息

        """
        segment = self.segment_service.get_segment(
            dataset_id,
            document_id,
            segment_id,
            current_user,
        )

        resp = GetSegmentResp()

        return success_json(resp.dump(segment))

    @route(
        "/<uuid:dataset_id>/document/<uuid:document_id>/segment/<uuid:segment_id>",
        methods=["POST"],
    )
    @swag_from(get_swagger_path("segment_handler/update_segment_enabled.yaml"))
    @login_required
    def update_segment_enabled(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
    ) -> Response:
        """更新文档片段启用状态接口。

        该接口用于启用或禁用指定的文档片段：
        1. 验证请求数据
        2. 调用服务层更新片段状态
        3. 返回更新结果

        Args:
            dataset_id (UUID): 数据集ID，用于标识所属知识库
            document_id (UUID): 文档ID，验证片段所属文档
            segment_id (UUID): 片段ID，指定要更新的片段

        Returns:
            Response: HTTP响应对象，包含状态更新结果

        Raises:
            ValidationError: 当请求数据验证失败时

        Note:
            请求方法: POST
            需要在请求体中提供新的启用状态

        """
        req = UpdateSegmentEnabledReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.segment_service.update_segment_enabled(
            dataset_id,
            document_id,
            segment_id,
            current_user,
            enabled=req.enabled.data,
        )

        return success_message_json("更新文档片段启用状态成功")

    @route(
        "/<uuid:dataset_id>/document/<uuid:document_id>/segment/<uuid:segment_id>/update",
        methods=["POST"],
    )
    @swag_from(get_swagger_path("segment_handler/update_segment.yaml"))
    @login_required
    def update_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
    ) -> Response:
        """根据传递的信息更新文档片段信息"""
        # 1.提取请求并校验
        req = UpdateSegmentReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务更新文档片段信息
        self.segment_service.update_segment(
            dataset_id,
            document_id,
            segment_id,
            req,
            current_user,
        )

        return success_message_json("更新文档片段成功")
