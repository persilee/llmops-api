from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)

from src.extension.database_extension import db


class UploadFile(db.Model):
    """上传文件表模型"""

    __tablename__ = "upload_file"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_upload_file_id"),
        UniqueConstraint("key", name="uk_upload_file_key"),
        UniqueConstraint("hash", name="uk_upload_file_hash"),
        Index("idx_upload_file_account_id", "account_id"),
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
        info={"description": "账号 id"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "原始文件名字"},
    )
    key = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "云端存储的文件路径"},
    )
    size = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "文件的尺寸大小，单位为字节"},
    )
    extension = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "文件的扩展名"},
    )
    mime_type = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "文件的 mimetype 类型推断"},
    )
    hash = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "文件内容的哈希值"},
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
