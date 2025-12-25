from dataclasses import dataclass

from injector import inject

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.core.builtin_apps.builtin_app_manager import BuiltinAppManager
from src.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from src.core.builtin_apps.entities.category_entity import CategoryEntity
from src.entity.app_entity import AppConfigType, AppStatus
from src.exception.exception import NotFoundException
from src.model.account import Account
from src.model.app import App, AppConfigVersion
from src.service.base_service import BaseService


@inject
@dataclass
class BuiltinAppService(BaseService):
    """内置应用服务类

    提供内置应用相关的核心业务功能，包括：
    - 获取应用分类
    - 获取内置应用列表
    - 将内置应用添加到工作空间

    Attributes:
        db: SQLAlchemy数据库实例，用于数据库操作
        builtin_app_manager: 内置应用管理器，用于管理内置应用的核心功能

    """

    db: SQLAlchemy
    builtin_app_manager: BuiltinAppManager

    def get_categories(self) -> list[CategoryEntity]:
        """获取所有内置应用的分类列表

        Returns:
            list[CategoryEntity]: 分类实体列表，包含所有内置应用的分类信息

        """
        return self.builtin_app_manager.get_categories()

    def get_builtin_apps(self) -> list[BuiltinAppEntity]:
        """获取所有内置应用列表

        Returns:
            list[BuiltinAppEntity]: 内置应用实体列表，包含所有内置应用的详细信息

        """
        return self.builtin_app_manager.get_builtin_apps()

    def add_builtin_app_to_space(self, builtin_app_id: str, account: Account) -> App:
        """将内置应用添加到用户空间

        Args:
            builtin_app_id (str): 内置应用的ID
            account (Account): 用户账户信息

        Returns:
            App: 创建的应用副本对象

        Raises:
            NotFoundException: 当内置应用不存在时抛出

        """
        # 获取内置应用
        builtin_app = self.builtin_app_manager.get_builtin_app(builtin_app_id)
        # 检查内置应用是否存在
        if not builtin_app:
            error_msg = "内置应用不存在"
            raise NotFoundException(error_msg)

        with self.db.auto_commit():
            # 创建应用副本
            app = App(
                account_id=account.id,
                status=AppStatus.DRAFT,
                name=builtin_app.name + "(副本)",
                **builtin_app.model_dump(include={"icon", "description"}),
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 创建应用配置
            draft_app_config = AppConfigVersion(
                app_id=app.id,
                model_config=builtin_app.language_model_config,
                config_type=AppConfigType.DRAFT,
                **builtin_app.model_dump(
                    include={
                        "dialog_round",
                        "preset_prompt",
                        "tools",
                        "retrieval_config",
                        "long_term_memory",
                        "opening_statement",
                        "opening_questions",
                        "speech_to_text",
                        "text_to_speech",
                        "review_config",
                        "suggested_after_answer",
                    },
                ),
            )
            self.db.session.add(draft_app_config)
            self.db.session.flush()

            # 关联应用配置
            app.draft_app_config_id = draft_app_config.id

        return app
