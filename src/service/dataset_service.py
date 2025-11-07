from dataclasses import dataclass

from injector import inject

from pkg.sqlalchemy import SQLAlchemy
from src.entity.dataset_entity import DEFAULT_DATASET_DESCRIPTION_FORMATTER
from src.exception.exception import ValidateErrorException
from src.model.dataset import Dataset
from src.schemas.dataset_schema import CreateDatasetReq
from src.service.base_service import BaseService


@inject
@dataclass
class DatasetService(BaseService):
    db: SQLAlchemy

    def create_dataset(self, req: CreateDatasetReq) -> Dataset:
        """创建新的数据集。

        Args:
            req (CreateDatasetReq): 创建数据集的请求对象，包含数据集的名称、
            图标和描述信息。

        Returns:
            Dataset: 创建成功的数据集对象。

        Raises:
            ValidateErrorException: 当数据集名称已存在时抛出此异常。

        Note:
            - 如果描述信息为空或仅包含空白字符，将使用默认格式生成描述。
            - 当前账户ID是硬编码的，实际应用中应该从认证信息中获取。

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 查询数据库中是否已存在相同账户ID和数据集名称的数据集
        dataset = (
            self.db.session.query(Dataset)
            .filter_by(
                account_id=account_id,  # 指定账户ID
                name=req.name.data,  # 指定数据集名称
            )
            .one_or_none()  # 返回一个结果或None
        )
        # 如果数据集已存在，抛出验证错误异常
        if dataset:
            error_msg = f"知识库名称为 {req.name.data} 已存在"
            raise ValidateErrorException(error_msg)
        # 如果描述信息为空或仅包含空白字符，使用默认格式生成描述
        if req.description.data is None or req.description.data.strip() == "":
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(
                name=req.name.data,  # 使用数据集名称格式化默认描述
            )

        # 创建新的数据集并返回
        return self.create(
            Dataset,  # 指定模型类
            account_id=account_id,  # 设置账户ID
            name=req.name.data,  # 设置数据集名称
            icon=req.icon.data,  # 设置数据集图标
            description=req.description.data,  # 设置数据集描述
        )
