from dataclasses import dataclass
from uuid import UUID

from injector import inject

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.model.dataset import KeywordTable
from src.service.base_service import BaseService


@inject
@dataclass
class KeywordTableService(BaseService):
    db: SQLAlchemy

    def get_keyword_table_form_dataset_id(self, dataset_id: UUID) -> KeywordTable:
        """根据数据集ID获取关键词表。如果不存在对应的关键词表，则创建一个新的空关键词表。

        Args:
            dataset_id (UUID): 数据集的唯一标识符

        Returns:
            KeywordTable: 关键词表对象，包含数据集ID和关键词表数据

        """
        # 查询数据库中是否存在对应数据集ID的关键词表
        keyword_table = (
            self.db.session.query(KeywordTable)
            .filter(
                KeywordTable.dataset_id == dataset_id,
            )
            .one_or_none()
        )
        # 如果不存在，则创建一个新的空关键词表
        if keyword_table is None:
            keyword_table = self.create(
                KeywordTable,
                dataset_id=dataset_id,
                keyword_table={},
            )

        return keyword_table
