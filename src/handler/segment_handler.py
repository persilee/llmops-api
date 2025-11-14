from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from flask import request
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
    GetSegmentResp,
    GetSegmentsWithPageReq,
    GetSegmentsWithPageResp,
    UpdateSegmentEnabledReq,
)
from src.service.segment_service import SegmentService


@inject
@dataclass
class SegmentHandler:
    segment_service: SegmentService

    @route("/<uuid:dataset_id>/documents/<uuid:document_id>/segments", methods=["GET"])
    @swag_from(get_swagger_path("segment_handler/get_segments_with_page.yaml"))
    def get_segments_with_page(self, dataset_id: UUID, document_id: UUID) -> Response:
        req = GetSegmentsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        segments, paginator = self.segment_service.get_segment_with_page(
            dataset_id,
            document_id,
            req,
        )

        resp = GetSegmentsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(segments), paginator=paginator))

    @route(
        "/<uuid:dataset_id>/document/<uuid:document_id>/segment/<uuid:segment_id>",
        methods=["GET"],
    )
    @swag_from(get_swagger_path("segment_handler/get_segment.yaml"))
    def get_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
    ) -> Response:
        segment = self.segment_service.get_segment(dataset_id, document_id, segment_id)

        resp = GetSegmentResp()

        return success_json(resp.dump(segment))

    @route(
        "/<uuid:dataset_id>/document/<uuid:document_id>/segment/<uuid:segment_id>",
        methods=["POST"],
    )
    @swag_from(get_swagger_path("segment_handler/update_segment_enabled.yaml"))
    def update_segment_enabled(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
    ) -> Response:
        req = UpdateSegmentEnabledReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.segment_service.update_segment_enabled(
            dataset_id,
            document_id,
            segment_id,
            enabled=req.enabled.data,
        )

        return success_message_json("更新文档片段启用状态成功")
