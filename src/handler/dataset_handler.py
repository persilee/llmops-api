from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from injector import inject

from pkg.response.response import (
    Response,
    success_json,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.dataset_schema import (
    CreateDatasetReq,
    GetDatasetResp,
    UpdateDatasetReq,
)
from src.service.dataset_service import DatasetService


@inject
@dataclass
class DatasetHandler:
    dataset_service: DatasetService

    @route("", methods=["POST"])
    @swag_from(get_swagger_path("dataset_handler/create_dataset.yaml"))
    def create_dataset(self) -> Response:
        """创建知识库

        通过POST请求创建知识库，接收请求数据并进行验证，
        验证通过后调用服务层创建数据集，最后返回创建结果

        Returns:
            Response: 包含创建结果的响应对象

        """
        # 创建请求数据对象
        req = CreateDatasetReq()
        # 验证请求数据
        if not req.validate():
            # 验证失败，返回错误信息
            return validate_error_json(req.errors)

        # 调用服务层创建知识库
        self.dataset_service.create_dataset(req)

        # 返回创建成功的响应
        return success_json("创建知识库成功")

    @route("/<uuid:dataset_id>", methods=["GET"])
    @swag_from(get_swagger_path("dataset_handler/get_dataset.yaml"))
    def get_dataset(self, dataset_id: UUID) -> Response:
        """获取单个知识库信息

        通过GET请求获取指定ID的知识库信息，
        调用服务层获取数据集，并将结果转换为响应格式返回

        Args:
            dataset_id (UUID): 知识库的唯一标识符

        Returns:
            Response: 包含知识库信息的响应对象

        """
        # 调用服务层获取指定ID的数据集
        dataset = self.dataset_service.get_dataset(dataset_id)
        # 创建响应数据对象
        resp = GetDatasetResp()

        # 返回包含知识库信息的成功响应
        return success_json(resp.dump(dataset))

    @route("/<uuid:dataset_id>", methods=["POST"])
    @swag_from(get_swagger_path("dataset_handler/update_dataset.yaml"))
    def update_dataset(self, dataset_id: UUID) -> Response:
        """更新知识库

        通过POST请求更新知识库，接收请求数据并进行验证，
        验证通过后调用服务层更新数据集，最后返回创建结果

        Returns:
            Response: 包含创建结果的响应对象

        """
        # 更新请求数据对象
        req = UpdateDatasetReq()
        # 验证请求数据
        if not req.validate():
            # 验证失败，返回错误信息
            return validate_error_json(req.errors)

        # 调用服务层更新知识库
        self.dataset_service.update_dataset(dataset_id, req)

        # 返回创建成功的响应
        return success_message_json("更新知识库成功")

    @route("", methods=["GET"])
    @swag_from(get_swagger_path("dataset_handler/get_datasets_with_page.yaml"))
    def get_datasets_with_page(self) -> Response:
        pass
