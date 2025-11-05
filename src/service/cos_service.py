import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from injector import inject
from qcloud_cos import CosConfig, CosS3Client, CosServiceError
from werkzeug.datastructures import FileStorage

from src.entity.upload_file_entity import (
    ALLOWED_DOCUMENT_EXTENSION,
    ALLOWED_IMAGE_EXTENSION,
)
from src.exception.exception import FailException
from src.model.upload_file import UploadFile
from src.service.upload_file_service import UploadFileService


@inject
@dataclass
class CosService:
    upload_file_service: UploadFileService

    def upload_file(self, file: FileStorage, *, only_image: bool = False) -> UploadFile:
        """上传文件到腾讯云对象存储(COS)

        Args:
            file (FileStorage): 要上传的文件对象
            only_image (bool, optional): 是否只允许上传图片文件. 默认为False

        Returns:
            UploadFile: 上传成功后的文件信息对象，包含文件名、存储路径、大小等信息

        Raises:
            ValueError: 当文件类型不符合要求时抛出
            FailException: 当文件上传失败时抛出

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"
        # 获取原始文件名和扩展名
        filename = file.filename
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        # 验证文件类型是否在允许的范围内
        if extension.lower() not in (
            ALLOWED_IMAGE_EXTENSION + ALLOWED_DOCUMENT_EXTENSION
        ):
            error_msg = f".{extension} 文件类型不允许上传"
            raise ValueError(error_msg)
        # 如果限制只上传图片，则验证文件类型是否为图片
        if only_image and extension not in ALLOWED_IMAGE_EXTENSION:
            error_msg = f".{extension} 图片类型不允许上传"
            raise ValueError(error_msg)

        # 初始化COS客户端和存储桶
        client = self._get_client()
        bucket = self._get_bucket()

        # 生成唯一的文件名，使用UUID避免文件名冲突
        random_filename = f"{uuid.uuid4()}.{extension}"
        # 按日期创建目录结构：年/月/日/文件名
        now = datetime.now(UTC)
        upload_filename = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"

        # 读取文件内容
        file_content = file.stream.read()
        file_hash = hashlib.sha3_256(file_content).hexdigest()

        try:
            # 检查文件是否已存在
            if self.upload_file_service.get_upload_file_by_hash(file_hash):
                error_msg = "文件已存在"
                raise FailException(error_msg)
            # 上传文件到COS
            client.put_object(bucket, file_content, upload_filename)
        except CosServiceError as e:
            error_msg = f"上传文件失败: {e}"
            raise FailException(error_msg) from e

        # 创建并返回文件记录，包含文件的所有元信息
        return self.upload_file_service.create_upload_file(
            account_id=account_id,
            name=filename,
            key=upload_filename,
            size=len(file_content),
            extension=extension,
            mime_type=file.content_type,
            # 使用SHA3-256算法计算文件哈希值，用于文件完整性校验
            hash=file_hash,
        )

    def download_file(self, key: str, target_file_path: str) -> None:
        """从COS下载文件到本地

        Args:
            key (str): COS中的文件键名
            target_file_path (str): 本地目标文件路径

        Returns:
            None

        Raises:
            CosServiceError: 当下载失败时抛出异常

        """
        # 获取COS客户端实例
        client = self._get_client()
        # 获取存储桶名称
        bucket = self._get_bucket()

        # 执行文件下载操作
        client.download_file(bucket, key, target_file_path)

    @classmethod
    def _get_client(cls) -> CosS3Client:
        """创建腾讯云COS客户端实例

        Returns:
            CosS3Client: 腾讯云COS客户端实例

        Note:
            从环境变量中读取COS配置信息：
            - COS_REGION: COS区域
            - COS_SECRET_ID: 访问密钥ID
            - COS_SECRET_KEY: 访问密钥Key
            - COS_SCHEME: 访问协议，默认为https

        """
        conf = CosConfig(
            Region=os.getenv("COS_REGION"),
            SecretId=os.getenv("COS_SECRET_ID"),
            SecretKey=os.getenv("COS_SECRET_KEY"),
            Token=None,
            Scheme=os.getenv("COS_SCHEME", "https"),
        )

        return CosS3Client(conf)

    @classmethod
    def _get_bucket(cls) -> str:
        """获取COS存储桶名称

        Args:
            cls: 类方法参数

        Returns:
            str: 从环境变量COS_BUCKET中获取的存储桶名称

        """
        return os.getenv("COS_BUCKET")

    def get_file_url(self, key: str) -> str:
        """生成文件的访问URL

        Args:
            key (str): 文件在COS中的存储路径

        Returns:
            str: 文件的完整访问URL

        """
        # 尝试从环境变量获取自定义的COS域名
        cos_domain = os.getenv("COS_DOMAIN")

        # 如果没有设置自定义域名，则使用默认的COS域名格式
        if not cos_domain:
            # 获取存储桶名称
            bucket = os.getenv("COS_BUCKET")
            # 获取协议类型（http/https）
            scheme = os.getenv("COS_SCHEME")
            # 获取COS区域
            region = os.getenv("COS_REGION")
            # 组装默认的COS访问域名
            cos_domain = f"{scheme}://{bucket}.cos.{region}.myqcloud.com"

        # 返回完整的文件访问URL
        return f"{cos_domain}/{key}"
