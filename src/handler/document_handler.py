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
from src.schemas.document_schema import (
    CreateDocumentReq,
    CreateDocumentResp,
    GetDocumentResp,
    GetDocumentsWithPageReq,
    GetDocumentsWithPageResp,
    UpdateDocumentEnabledReq,
    UpdateDocumentNameReq,
)
from src.service.document_service import DocumentService


@inject
@dataclass
class DocumentHandler:
    document_service: DocumentService

    @route("/<uuid:dataset_id>/document/<uuid:document_id>/enabled", methods=["POST"])
    @swag_from(get_swagger_path("dataset_handler/update_document_enabled.yaml"))
    def update_document_enabled(self, dataset_id: UUID, document_id: UUID) -> Response:
        """更新文档的启用状态

        Args:
            dataset_id (UUID): 数据集ID
            document_id (UUID): 文档ID

        Returns:
            Response: 包含操作结果的响应对象
                - 成功时返回成功消息
                - 验证失败时返回错误信息

        """
        req = UpdateDocumentEnabledReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.document_service.update_document_enabled(
            dataset_id,
            document_id,
            enabled=req.enabled.data,
        )

        return success_message_json("更新文档启用状态成功")

    @route("/<uuid:dataset_id>/document/<uuid:document_id>", methods=["GET"])
    @swag_from(get_swagger_path("dataset_handler/get_document.yaml"))
    def get_document(self, dataset_id: UUID, document_id: UUID) -> Response:
        """获取单个文档信息

        Args:
            dataset_id (UUID): 数据集ID
            document_id (UUID): 文档ID

        Returns:
            Response: 包含文档信息的成功响应

        """
        document = self.document_service.get_document(dataset_id, document_id)

        resp = GetDocumentResp()

        return success_json(resp.dump(document))

    @route("/<uuid:dataset_id>/document/<uuid:document_id>/name", methods=["POST"])
    @swag_from(get_swagger_path("dataset_handler/update_document_name.yaml"))
    def update_document_name(self, dataset_id: UUID, document_id: UUID) -> Response:
        # 创建更新文档名称的请求对象
        req = UpdateDocumentNameReq()
        # 验证请求数据的合法性
        if not req.validate():
            # 如果验证失败，返回验证错误信息
            return validate_error_json(req.errors)

        # 调用服务层方法更新文档名称
        self.document_service.update_document_name(
            dataset_id,  # 数据集ID
            document_id,  # 文档ID
            name=req.name.data,  # 新的文档名称
        )

        # 返回成功响应，提示文档名称更新成功
        return success_message_json("文档名称更新成功")

    @route("/<uuid:dataset_id>/documents", methods=["GET"])
    @swag_from(get_swagger_path("dataset_handler/get_documents_with_page.yaml"))
    def get_documents_with_page(self, dataset_id: UUID) -> Response:
        # 创建请求对象，解析查询参数
        req = GetDocumentsWithPageReq(request.args)
        # 验证请求数据的合法性
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用服务层获取分页文档列表
        documents, paginator = self.document_service.get_documents_with_page(
            dataset_id,
            req,
        )

        # 创建响应对象，用于序列化文档列表
        resp = GetDocumentsWithPageResp(many=True)

        # 返回成功响应，包含文档列表和分页信息
        return success_json(PageModel(list=resp.dump(documents), paginator=paginator))

    @route("/<uuid:dataset_id>/documents", methods=["POST"])
    @swag_from(get_swagger_path("dataset_handler/create_documents.yaml"))
    def create_documents(self, dataset_id: UUID) -> Response:
        """创建文档接口

        Args:
            dataset_id (UUID): 数据集ID

        Returns:
            Response: 包含创建结果的响应对象

        """
        # 创建请求对象
        req = CreateDocumentReq()
        # 验证请求数据
        if not req.validate():
            return validate_error_json(req.errors)
        # 调用服务层创建文档
        documents, batch = self.document_service.create_documents(
            dataset_id,
            **req.data,
        )

        # 创建响应对象
        resp = CreateDocumentResp()

        # 返回成功响应，包含创建的文档和批次信息
        return success_json(resp.dump((documents, batch)))

    @route("/<uuid:dataset_id>/documents/batch/<string:batch>", methods=["POST"])
    @swag_from(get_swagger_path("dataset_handler/get_documents_status.yaml"))
    def get_documents_status(self, dataset_id: UUID, batch: str) -> Response:
        """获取文档状态接口

        Args:
            dataset_id (UUID): 数据集ID
            batch (str): 批次

        Returns:
            Response: 包含文档状态的响应对象

        """
        documents_status = self.document_service.get_documents_status(dataset_id, batch)

        return success_json(documents_status)
