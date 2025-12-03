from dataclasses import dataclass

from flasgger import swag_from
from flask_login import current_user, login_required
from injector import inject

from pkg.response.response import (
    Response,
    success_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.upload_file_schema import UploadFileReq, UploadFileResp, UploadImageReq
from src.service.cos_service import CosService


@inject
@dataclass
class UploadFileHandler:
    cos_service: CosService

    @route("/upload-file", methods=["POST"])
    @swag_from(get_swagger_path("upload_file_handler/upload_file.yaml"))
    @login_required
    def upload_file(self) -> Response:
        """处理文件上传请求

        Returns:
            Response: 包含上传结果的响应对象

        """
        # 创建上传文件请求对象
        req = UploadFileReq()
        # 验证请求数据是否有效
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用COS服务上传文件
        upload_file = self.cos_service.upload_file(req.file.data, current_user)

        # 创建响应对象
        resp = UploadFileResp()

        # 返回成功响应，包含上传结果
        return success_json(resp.dump(upload_file))

    @route("/upload-image", methods=["POST"])
    @swag_from(get_swagger_path("upload_file_handler/upload_image.yaml"))
    @login_required
    def upload_image(self) -> Response:
        """处理图片上传请求

        该方法接收图片上传请求，验证请求数据，将图片上传到COS服务，
        获取图片访问URL并返回响应。

        Returns:
            Response: 包含图片URL的响应对象，格式为 {"url": image_url}

        Raises:
            ValidationError: 当请求数据验证失败时抛出

        """
        # 创建图片上传请求对象
        req = UploadImageReq()
        # 验证请求数据是否有效
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用COS服务上传图片，only_image=True确保只允许图片格式
        upload_file = self.cos_service.upload_file(
            req.file.data,
            current_user,
            only_image=True,
        )
        # 获取上传后图片的访问URL
        image_url = self.cos_service.get_file_url(upload_file.key)

        # 返回成功响应，包含图片URL
        return success_json({"url": image_url})
