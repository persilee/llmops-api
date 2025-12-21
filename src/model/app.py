"""应用模型模块.

该模块定义了应用程序的数据库模型，包含应用的基本信息，
如ID、所属账户ID、名称、图标、描述以及时间戳等字段。
"""

from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.entity.app_entity import DEFAULT_APP_CONFIG, AppConfigType
from src.entity.conversation_entity import InvokeFrom
from src.extension import db
from src.model.conversation import Conversation


class App(db.Model):
    """应用模型"""

    __tablename__ = "app"
    __table_args__ = (PrimaryKeyConstraint("id", name="pk_app_id"),)

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    account_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联的账号 id"},
    )
    app_config_id = Column(
        UUID,
        nullable=True,
        info={"description": "发布的配置 id，当值为空时，表示没有发布"},
    )
    draft_app_config_id = Column(
        UUID,
        nullable=True,
        info={"description": "草稿配置 id"},
    )
    debug_conversation_id = Column(
        UUID,
        nullable=True,
        info={"description": "调试会话 id"},
    )
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "应用名称"},
    )
    icon = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "应用图标"},
    )
    description = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "应用描述"},
    )
    status = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "应用的状态"},
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
    def draft_app_config(self) -> "AppConfigVersion":
        app_config_version = (
            db.session.query(AppConfigVersion)
            .filter(
                AppConfigVersion.app_id == self.id,
                AppConfigVersion.config_type == AppConfigType.DRAFT,
            )
            .one_or_none()
        )

        if not app_config_version:
            app_config_version = AppConfigVersion(
                app_id=self.id,
                version=1,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG,
            )
            db.session.add(app_config_version)
            db.session.commit()

        return app_config_version

    @property
    def debug_conversation(self) -> "Conversation":
        debug_conversation = None
        if self.debug_conversation_id is not None:
            debug_conversation = (
                db.session.query(Conversation)
                .filter(
                    Conversation.id == self.debug_conversation_id,
                    Conversation.invoke_from == InvokeFrom.DEBUGGER,
                )
                .one_or_none()
            )

        if not self.debug_conversation_id or not debug_conversation:
            with db.auto_commit():
                debug_conversation = Conversation(
                    app_id=self.id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.DEBUGGER,
                    created_by=self.account_id,
                )
                db.session.add(debug_conversation)
                db.session.flush()
                self.debug_conversation_id = debug_conversation.id

        return debug_conversation


class AppDatasetJoin(db.Model):
    """知识库关联表模型（应用与知识库的关联关系）"""

    __tablename__ = "app_dataset_join"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_dataset_join_id"),
        # 联合唯一约束：确保同一应用与同一知识库仅存在一条关联记录
        UniqueConstraint(
            "app_id",
            "dataset_id",
            name="uk_app_dataset_join_app_dataset",
        ),
        Index("idx_app_dataset_join_app_id", "app_id"),
        Index("idx_app_dataset_join_dataset_id", "dataset_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    app_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联应用 id"},
    )
    dataset_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联知识库 id"},
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


class AppConfig(db.Model):
    """应用配置模型"""

    __tablename__ = "app_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_id"),
        Index("idx_app_config_app_id", "app_id"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    app_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联应用 id"},
    )
    model_config = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "模型配置信息"},
    )
    dialog_round = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "上下文轮数"},
    )
    preset_prompt = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "预设提示词"},
    )
    tools = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "应用关联列表"},
    )
    workflows = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "应用关联工作流列表"},
    )
    retrieval_config = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "检索配置"},
    )
    long_term_memory = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "长期记忆配置"},
    )
    opening_statement = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "开场白文案"},
    )
    opening_questions = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "开场白建议问题"},
    )
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
        info={"description": "对话后自动生成建议问题"},
    )
    speech_to_text = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "语音转文本配置"},
    )
    text_to_speech = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "文本转语音配置"},
    )
    review_config = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "审核配置"},
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


class AppConfigVersion(db.Model):
    """应用配置历史模型"""

    __tablename__ = "app_config_version"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_version_id"),
        UniqueConstraint(
            "app_id",
            "version",
            name="uk_app_config_version_app_id_version",
        ),
        Index("idx_app_config_version_app_id", "app_id"),
        Index("idx_app_config_version_config_type", "config_type"),
    )

    id = Column(
        UUID,
        nullable=False,
        server_default=text("uuid_generate_v4()"),
        info={"description": "表 id"},
    )
    app_id = Column(
        UUID,
        nullable=False,
        info={"description": "关联应用 id"},
    )
    datasets = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "关联知识库列表"},
    )
    model_config = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "模型配置信息"},
    )
    dialog_round = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        info={"description": "上下文轮数"},
    )
    preset_prompt = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "预设提示词"},
    )
    tools = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "应用关联列表"},
    )
    workflows = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "应用关联工作流列表"},
    )
    retrieval_config = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "检索配置"},
    )
    long_term_memory = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "长期记忆配置"},
    )
    opening_statement = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        info={"description": "开场白文案"},
    )
    opening_questions = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        info={"description": "开场白建议问题"},
    )
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
        info={"description": "对话后自动生成建议问题"},
    )
    speech_to_text = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "语音转文本配置"},
    )
    text_to_speech = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "文本转语音配置"},
    )
    review_config = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        info={"description": "审核配置"},
    )
    version = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        info={"description": "版本号"},
    )
    config_type = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        info={"description": "配置的类型"},
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
