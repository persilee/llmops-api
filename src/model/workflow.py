from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Float,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.extension.database_extension import db


class Workflow(db.Model):
    """Workflow 工作流模型"""

    __tablename__ = "workflow"
    __table_args__ = (PrimaryKeyConstraint("id", name="pk_workflow_id"),)

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表主键id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联账户id"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "工作流名称"},
    )
    tool_call_name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "工作流调用工具名称"},
    )
    icon = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "图标"},
    )
    description = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "描述"},
    )
    graph = Column(
        JSONB,
        nullable=False,
        info={"description": "运行时配置"},
        server_default=text("'{}'::jsonb"),
    )
    draft_graph = Column(
        JSONB,
        nullable=False,
        info={"description": "草稿图配置"},
        server_default=text("'{}'::jsonb"),
    )
    is_debug_passed = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        info={"description": "是否调试通过"},
    )
    status = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "状态"},
    )
    published_at = Column(
        DateTime,
        nullable=True,
        info={"description": "发布时间"},
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


class WorkflowResult(db.Model):
    """WorkflowResult 工作流结果存储模型"""

    __tablename__ = "workflow_result"
    __table_args__ = (PrimaryKeyConstraint("id", name="pk_workflow_result_id"),)

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表主键id"},
    )
    app_id = Column(
        UUID,
        nullable=True,
        info={"description": "关联应用id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联账户id"},
    )
    workflow_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联工作流id"},
    )
    graph = Column(
        JSONB,
        nullable=False,
        info={"description": "运行时配置"},
        server_default=text("'{}'::jsonb"),
    )
    status = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "运行状态"},
    )
    state = Column(
        JSONB,
        nullable=False,
        info={"description": "最终状态"},
        server_default=text("'{}'::jsonb"),
    )
    latency = Column(
        Float,
        nullable=False,
        info={"description": "总耗时"},
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
