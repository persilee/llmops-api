from typing import Any

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired, FileSize
from marshmallow import Schema, fields, pre_dump

from src.entity.upload_file_entity import (
    ALLOWED_DOCUMENT_EXTENSION,
    ALLOWED_IMAGE_EXTENSION,
)
from src.model.upload_file import UploadFile


class UploadFileReq(FlaskForm):
    """文件上传请求表单类

    用于验证上传文件的表单，包含以下验证规则：
    1. 文件不能为空
    2. 文件大小不能超过15MB
    3. 文件类型必须是允许的文档类型
    """

    file = FileField(
        "file",  # 表单字段名称
        validators=[
            FileRequired("上传文件不能为空"),  # 验证文件是否为空
            FileSize(
                max_size=15 * 1024 * 1024,
                message="文件大小不能超过15MB",
            ),  # 验证文件大小限制
            FileAllowed(
                ALLOWED_DOCUMENT_EXTENSION,  # 允许的文件扩展名列表
                message=f"仅允许上传{'/'.join(ALLOWED_DOCUMENT_EXTENSION)}的文件",
            ),
        ],
    )


class UploadFileResp(Schema):
    """文件上传响应Schema类

    用于序列化文件上传响应数据的Schema，包含以下字段：
    - id: 文件唯一标识符
    - account_id: 上传用户的账户ID
    - name: 文件名
    - key: 文件在存储系统中的唯一键
    - size: 文件大小（字节）
    - extension: 文件扩展名
    - mime_type: 文件MIME类型
    - created_at: 文件创建时间（时间戳）
    """

    # 文件唯一标识符
    id = fields.UUID(dump_default="")
    # 上传用户的账户ID
    account_id = fields.UUID(dump_default="")
    # 文件名
    name = fields.String(dump_default="")
    # 文件在存储系统中的唯一键
    key = fields.String(dump_default="")
    # 文件大小（字节）
    size = fields.Integer(dump_default=0)
    # 文件扩展名
    extension = fields.String(dump_default="")
    # 文件MIME类型
    mime_type = fields.String(dump_default="")
    # 文件创建时间（时间戳）
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: UploadFile, **kwargs: Any) -> dict:
        """处理上传文件数据

        在序列化之前处理UploadFile对象，将其转换为字典格式。
        特别处理created_at字段，将datetime对象转换为时间戳。

        Args:
            data: UploadFile对象，包含文件的所有信息
            **kwargs: 其他关键字参数

        Returns:
            dict: 包含所有文件信息的字典，其中created_at已转换为时间戳

        """
        return {
            "id": data.id,
            "account_id": data.account_id,
            "name": data.name,
            "key": data.key,
            "size": data.size,
            "extension": data.extension,
            "mime_type": data.mime_type,
            "created_at": int(data.created_at.timestamp()),
        }


class UploadImageReq(FlaskForm):
    """图片上传请求表单类。

    用于验证上传图片的表单数据，包括：
    - 验证文件是否为空
    - 验证文件大小不超过15MB
    - 验证文件类型是否为允许的图片格式
    """

    file = FileField(
        "file",  # 表单字段名称
        validators=[
            FileRequired("上传图片不能为空"),  # 验证图片是否为空
            FileSize(
                max_size=15 * 1024 * 1024,
                message="图片大小不能超过15MB",
            ),  # 验证图片大小限制
            FileAllowed(
                ALLOWED_IMAGE_EXTENSION,  # 允许的文件扩展名列表
                message=f"仅允许上传{'/'.join(ALLOWED_IMAGE_EXTENSION)}的类型的图片",
            ),
        ],
    )
