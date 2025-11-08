from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import select

from pkg.paginator.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from src.entity.dataset_entity import DEFAULT_DATASET_DESCRIPTION_FORMATTER
from src.exception.exception import NotFoundException, ValidateErrorException
from src.model.dataset import Dataset
from src.schemas.dataset_schema import (
    CreateDatasetReq,
    GetDatasetsWithPageReq,
    UpdateDatasetReq,
)
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

    def get_dataset(self, dataset_id: UUID) -> Dataset:
        """获取指定的知识库。

        Args:
            dataset_id (UUID): 要获取的数据集的唯一标识符。

        Returns:
            Dataset: 获取到的数据集对象。

        Raises:
            NotFoundException: 当数据集不存在或不属于当前账户时抛出此异常。

        Note:
            - 当前账户ID是硬编码的，实际应用中应该从认证信息中获取。
            - 会同时验证数据集是否存在以及是否属于当前账户。

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            error_msg = f"知识库ID为 {dataset_id} 不存在"
            raise NotFoundException(error_msg)

        return dataset

    def update_dataset(self, dataset_id: UUID, req: UpdateDatasetReq) -> Dataset:
        """更新知识库信息。

        Args:
            dataset_id (UUID): 要更新的知识库ID
            req (UpdateDatasetReq): 更新请求对象，包含新的知识库信息

        Returns:
            Dataset: 更新后的知识库对象

        Raises:
            NotFoundException: 当知识库不存在或不属于当前账户时
            ValidateErrorException: 当知识库名称已存在时

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"
        # 根据知识库ID获取知识库信息
        dataset = self.get(Dataset, dataset_id)
        # 验证知识库是否存在且属于当前账户
        if dataset is None or str(dataset.account_id) != account_id:
            error_msg = f"知识库ID为 {dataset_id} 不存在"
            raise NotFoundException(error_msg)

        # 查询是否存在同名的知识库（排除当前知识库）
        check_dataset = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.account_id == account_id,  # 限定在同一账户下
                Dataset.name == req.name.data,  # 检查名称是否重复
                Dataset.id != dataset_id,  # 排除当前知识库
            )
            .one_or_none()
        )
        # 如果存在同名知识库，抛出验证错误异常
        if check_dataset:
            error_msg = f"知识库名称为 {req.name.data} 已存在"
            raise ValidateErrorException(error_msg)

        # 如果描述信息为空或仅包含空白字符，使用默认格式生成描述
        if req.description.data is None or req.description.data.strip() == "":
            # 使用知识库名称格式化默认描述信息
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(
                name=req.name.data,
            )

        # 更新知识库信息
        self.update(
            dataset,
            name=req.name.data,  # 更新名称
            icon=req.icon.data,  # 更新图标
            description=req.description.data,  # 更新描述
        )

        # 返回更新后的知识库信息
        return dataset

    def get_datasets_with_page(
        self,
        req: GetDatasetsWithPageReq,
    ) -> tuple[list[Dataset], Paginator]:
        """分页获取知识库列表。

        Args:
            req: 分页查询请求对象，包含分页参数和搜索条件

        Returns:
            tuple[list[Dataset], Paginator]: 返回一个元组，包含知识库列表和分页器对象
                - list[Dataset]: 符合条件的知识库列表
                - Paginator: 包含分页信息的分页器对象

        Note:
            当前使用固定的账户ID，实际应用中应该从认证信息中获取

        """
        # TODO: 设置账户ID，实际应用中应该从认证信息中获取
        account_id = "9495d2e2-2e7a-4484-8447-03f6b24627f7"

        # 创建分页器实例，用于处理分页逻辑
        paginator = Paginator(db=self.db, req=req)

        # 构建基础查询语句，筛选属于当前账户的知识库
        stmt = select(Dataset).where(Dataset.account_id == account_id)
        # 如果提供了搜索关键词，添加模糊搜索条件
        if req.search_word.data:
            stmt = stmt.where(Dataset.name.ilike(f"%{req.search_word.data}%"))

        # 按创建时间降序排序
        stmt = stmt.order_by(Dataset.created_at.desc())

        # 执行分页查询
        datasets = paginator.paginate(stmt)

        # 返回查询结果和分页器信息
        return datasets, paginator
