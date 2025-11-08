from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.extension.database_extension import db
from src.model.app import AppDatasetJoin
from src.schemas.swag_schema import swagger_schema


@swagger_schema
class Dataset(db.Model):
    """知识库模型"""

    __tablename__ = "dataset"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_dataset_id"),
        Index("idx_dataset_account_id", "account_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联用户 id"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "知识库名称"},
    )
    icon = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "知识库图标"},
    )
    description = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "知识库描述"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )

    @property
    def document_count(self) -> int:
        return (
            db.session.query(func.count(Document.id))
            .filter(
                Document.dataset_id == self.id,
            )
            .scalar()
        )

    @property
    def hit_count(self) -> int:
        return (
            db.session.query(func.coalesce(func.sum(Segment.hit_count), 0))
            .filter(
                Segment.dataset_id == self.id,
            )
            .scalar()
        )

    @property
    def character_count(self) -> int:
        return (
            db.session.query(func.coalesce(func.sum(Document.character_count), 0))
            .filter(
                Document.dataset_id == self.id,
            )
            .scalar()
        )

    @property
    def related_app_count(self) -> int:
        return (
            db.session.query(func.count(AppDatasetJoin.id))
            .filter(
                AppDatasetJoin.dataset_id == self.id,
            )
            .scalar()
        )


@swagger_schema
class Document(db.Model):
    """文档模型"""

    __tablename__ = "document"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_document_id"),
        Index("idx_document_account_id", "account_id"),
        Index("idx_document_dataset_id", "dataset_id"),
        Index("idx_document_upload_file_id", "upload_file_id"),
        Index("idx_document_process_rule_id", "process_rule_id"),
        Index("idx_document_batch", "batch"),
        Index("idx_document_status", "status"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联用户 id"},
    )
    dataset_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联知识库 id"},
    )
    upload_file_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联文件上传表 id"},
    )
    process_rule_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联编排规则表 id"},
    )
    batch = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "文档的批次"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "文档的名字"},
    )
    position = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        info={"description": "文档的位置"},
    )
    character_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "文档的字符总数"},
    )
    token_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "文档的 token 总数"},
    )
    processing_started_at = Column(
        DateTime,
        nullable=True,
        info={"description": "处理开始时间"},
    )
    parsing_completed_at = Column(
        DateTime,
        nullable=True,
        info={"description": "解析完成时间"},
    )
    splitting_completed_at = Column(
        DateTime,
        nullable=True,
        info={"description": "分割完成时间"},
    )
    indexing_completed_at = Column(
        DateTime,
        nullable=True,
        info={"description": "构建索引完成时间"},
    )
    completed_at = Column(
        DateTime,
        nullable=True,
        info={"description": "完成时间"},
    )
    stopped = Column(
        DateTime,
        nullable=True,
        info={"description": "停止时间"},
    )
    error = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "发生错误日志"},
    )
    enabled = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        info={"description": "是否启用"},
    )
    disabled_at = Column(
        DateTime,
        nullable=True,
        info={"description": "禁用时间"},
    )
    status = Column(
        String(255),
        nullable=False,
        server_default=text("'waiting'::character varying"),
        info={"description": "文档的状态"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )


@swagger_schema
class Segment(db.Model):
    """文档片段模型"""

    __tablename__ = "segment"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_segment_id"),
        UniqueConstraint("hash", name="uk_segment_hash"),  # 片段哈希值唯一
        Index("idx_segment_account_id", "account_id"),
        Index("idx_segment_dataset_id", "dataset_id"),
        Index("idx_segment_document_id", "document_id"),
        Index("idx_segment_node_id", "node_id"),
        Index("idx_segment_status", "status"),
        Index("idx_segment_enabled", "enabled"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联用户 id"},
    )
    dataset_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联知识库 id"},
    )
    document_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联文档表 id"},
    )
    node_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联节点表 id"},
    )
    position = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        info={"description": "片段位置"},
    )
    content = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "片段的内容"},
    )
    character_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "片段的字符总数"},
    )
    token_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "片段的 token 总数"},
    )
    keywords = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "关键词"},
    )
    hash = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "片段的哈希值"},
    )
    hit_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "命中次数"},
    )
    enabled = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        info={"description": "是否启用"},
    )
    disabled_at = Column(
        DateTime,
        nullable=True,
        info={"description": "禁用时间"},
    )
    processing_started_at = Column(
        DateTime,
        nullable=True,
        info={"description": "处理开始时间"},
    )
    indexing_completed_at = Column(
        DateTime,
        nullable=True,
        info={"description": "构建索引完成时间"},
    )
    completed_at = Column(
        DateTime,
        nullable=True,
        info={"description": "完成时间"},
    )
    stopped = Column(
        DateTime,
        nullable=True,
        info={"description": "停止时间"},
    )
    error = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "发生错误日志"},
    )
    status = Column(
        String(255),
        nullable=False,
        server_default=text("'waiting'::character varying"),
        info={"description": "片段的状态"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )


@swagger_schema
class KeywordTable(db.Model):
    """关键词表模型"""

    __tablename__ = "keyword_table"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_keyword_table_id"),
        Index("idx_keyword_table_dataset_id", "dataset_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    dataset_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联知识库 id"},
    )
    keyword_table = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "关键词表数据"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )


@swagger_schema
class DatasetQuery(db.Model):
    """知识库查询表模型"""

    __tablename__ = "dataset_query"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_dataset_query_id"),
        Index("idx_dataset_query_dataset_id", "dataset_id"),
        Index("idx_dataset_query_created_by", "created_by"),
        Index("idx_dataset_query_source_app_id", "source_app_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    dataset_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联知识库 id"},
    )
    query = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "查询语句"},
    )
    source = Column(
        String(255),
        nullable=False,
        server_default=text("'HitTesting'::character varying"),
        info={"description": "查询来源"},
    )
    source_app_id = Column(
        UUID,
        nullable=True,
        info={"description": "来源应用 id"},
    )
    created_by = Column(
        UUID,
        nullable=True,
        info={"description": "创建人 id"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )


@swagger_schema
class ProcessRule(db.Model):
    """文档处理规则表模型"""

    __tablename__ = "process_rule"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_process_rule_id"),
        Index("idx_process_rule_account_id", "account_id"),
        Index("idx_process_rule_dataset_id", "dataset_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联用户 id"},
    )
    dataset_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联知识库 id"},
    )
    mode = Column(
        String(255),
        nullable=False,
        server_default=text("'automic'::character varying"),
        info={"description": "处理模式"},
    )
    rule = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "处理规则配置"},
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "更新时间"},
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        info={"description": "创建时间"},
    )
