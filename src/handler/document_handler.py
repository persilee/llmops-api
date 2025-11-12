from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from injector import inject

from pkg.response.response import Response, success_json, validate_error_json
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.document_schema import CreateDocumentReq, CreateDocumentResp
from src.service.document_service import DocumentService


@inject
@dataclass
class DocumentHandler:
    document_service: DocumentService

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
