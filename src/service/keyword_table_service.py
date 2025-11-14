from dataclasses import dataclass
from uuid import UUID

from injector import inject
from redis import Redis

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.entity.cache_entity import (
    LOCK_EXPIRE_TIME,
    LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE,
)
from src.model.dataset import KeywordTable, Segment
from src.service.base_service import BaseService


@inject
@dataclass
class KeywordTableService(BaseService):
    db: SQLAlchemy
    redis_client: Redis

    def get_keyword_table_from_dataset_id(self, dataset_id: UUID) -> KeywordTable:
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

    def delete_keyword_table_from_ids(
        self,
        dataset_id: UUID,
        segment_ids: list[UUID],
    ) -> None:
        """从关键词表中删除指定segment_id对应的关键词。

        Args:
            dataset_id: 数据集ID
            segment_ids: 要删除的segment ID列表

        """
        # 生成分布式锁的key，确保并发安全
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(
            dataset_id=dataset_id,
        )
        # 使用分布式锁保护关键词表更新操作
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            # 获取当前数据集的关键词表记录
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)
            # 创建关键词表的副本，避免直接修改原数据
            keyword_table = keyword_table_record.keyword_table.copy()

            # 将要删除的segment_id转换为字符串集合，便于比较
            segment_ids_to_delete = {str(segment_id) for segment_id in segment_ids}

            # 初始化需要删除的关键词集合
            keywords_to_delete = set()

            # 遍历关键词表中的每个关键词及其关联的segment_id列表
            for keyword, ids in keyword_table.items():
                # 将segment_id列表转换为集合，便于集合操作
                ids_set = set(ids)
                # 如果当前关键词关联的segment_id与要删除的segment_id有交集
                if segment_ids_to_delete.intersection(ids_set):
                    # 从关键词的segment_id列表中移除要删除的segment_id
                    keyword_table[keyword] = list(
                        ids_set.difference(segment_ids_to_delete),
                    )
                    # 如果删除后该关键词没有关联的segment_id，则标记该关键词需要删除
                    if not keyword_table[keyword]:
                        keywords_to_delete.add(keyword)

            # 删除没有关联segment_id的关键词
            for keyword in keywords_to_delete:
                del keyword_table[keyword]

            # 更新数据库中的关键词表记录
            self.update(keyword_table_record, keyword_table=keyword_table)

    def add_keyword_table_from_ids(
        self,
        dataset_id: UUID,
        segment_ids: list[UUID],
    ) -> None:
        """向指定数据集的关键词表中添加新的段落ID。

        该方法会更新关键词表，将指定段落ID列表中的段落添加到对应关键词的集合中。
        使用分布式锁确保并发操作的安全性。

        Args:
            dataset_id (UUID): 数据集的唯一标识符
            segment_ids (list[UUID]): 需要添加到关键词表的段落ID列表

        Returns:
            None

        """
        # 生成分布式锁的key，用于保护关键词表更新操作的并发安全
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(
            dataset_id=dataset_id,
        )
        # 使用分布式锁确保同一时间只有一个进程可以更新关键词表
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            # 获取指定数据集ID对应的关键词表记录
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)
            # 将关键词表中的每个字段值转换为set集合，便于后续的添加操作
            keyword_table = {
                field: set(value)
                for field, value in keyword_table_record.keyword_table.items()
            }

            # 查询数据库中指定ID列表的段落，只获取id和keywords字段
            segments = (
                self.db.session.query(Segment)
                .with_entities(Segment.id, Segment.keywords)
                .filter(
                    Segment.id.in_(segment_ids),
                )
                .all()
            )

            # 遍历查询到的段落，更新关键词表
            for id, keywords in segments:
                # 对每个段落中的关键词进行处理
                for keyword in keywords:
                    # 如果关键词不存在于关键词表中，则创建新的条目
                    if keyword not in keyword_table:
                        keyword_table[keyword] = set()
                    # 将当前段落ID添加到该关键词对应的段落ID集合中
                    keyword_table[keyword].add(str(id))

            # 更新数据库中的关键词表记录
            # 将set集合转换回list格式，以便存储到数据库
            self.update(
                keyword_table_record,
                keyword_table={
                    field: list(value) for field, value in keyword_table.items()
                },
            )
