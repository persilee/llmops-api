import uuid
from dataclasses import dataclass

from injector import inject

from pkg.sqlalchemy import SQLAlchemy
from src.entity.app_entity import DEFAULT_APP_CONFIG, AppConfigType, AppStatus
from src.exception.exception import ForbiddenException, NotFoundException
from src.model import App
from src.model.account import Account
from src.model.app import AppConfigVersion
from src.schemas.app_schema import CreateAppReq
from src.service.base_service import BaseService


@inject
@dataclass
class AppService(BaseService):
    db: SQLAlchemy

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """创建新应用

        Args:
            req: 创建应用的请求参数，包含应用名称、图标、描述等信息
            account: 创建应用的用户账号信息

        Returns:
            App: 创建成功的应用对象

        """
        # 使用数据库事务上下文，确保操作的原子性
        with self.db.auto_commit():
            # 创建应用实体对象
            app = App(
                account_id=account.id,  # 关联用户ID
                name=req.name.data,  # 应用名称
                icon=req.icon.data,  # 应用图标
                description=req.description.data,  # 应用描述
                status=AppStatus.DRAFT,  # 初始状态为草稿
            )
            # 将应用对象添加到数据库会话中
            self.db.session.add(app)
            # 刷新会话，获取应用ID
            self.db.session.flush()

            # 创建应用配置版本对象
            app_config_version = AppConfigVersion(
                app_id=app.id,  # 关联应用ID
                version=1,  # 初始版本号
                config_type=AppConfigType.DRAFT,  # 配置类型为草稿
                **DEFAULT_APP_CONFIG,  # 使用默认配置
            )
            # 将配置版本对象添加到数据库会话中
            self.db.session.add(app_config_version)
            # 刷新会话，获取配置版本ID
            self.db.session.flush()

            # 将草稿配置ID关联到应用对象
            app.draft_app_config_id = app_config_version.id

        # 返回创建的应用对象
        return app

    def get_app(self, app_id: uuid.UUID, account: Account) -> App:
        """获取应用信息

        Args:
            app_id: 应用ID，用于唯一标识一个应用
            account: 用户账号信息，用于验证应用所有权

        Returns:
            App: 返回获取到的应用对象

        Raises:
            NotFoundException: 当应用不存在时抛出
            ForbiddenException: 当应用不属于当前用户时抛出

        """
        # 根据应用ID查询应用信息
        app = self.get(App, app_id)
        # 检查应用是否存在
        if not app:
            error_msg = f"应用 {app_id} 不存在"
            raise NotFoundException(error_msg)

        # 验证应用所有权，确保只有应用所有者才能访问
        if app.account_id != account.id:
            error_msg = f"应用 {app_id} 不属于当前用户"
            raise ForbiddenException(error_msg)

        # 返回应用对象
        return app

    def update_app(self, app_id: uuid.UUID) -> App:
        with self.db.auto_commit():
            app: App = self.get_app(app_id)
            app.name = "聊天机器人6"

        return app

    def delete_app(self, app_id: uuid.UUID) -> App:
        with self.db.auto_commit():
            app: App = self.get_app(app_id)
            self.db.session.delete(app)

        return app
