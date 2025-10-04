import uuid
from dataclasses import dataclass

from injector import inject

from pkg.sqlalchemy import SQLAlchemy
from src.model import App


@inject
@dataclass
class AppService:
    db: SQLAlchemy

    def create_app(self) -> App:
        with self.db.auto_commit():
            app = App(
                name="聊天机器人",
                account_id=uuid.uuid4(),
                icon="https://example.com/icon.png",
                description="一个聊天机器人",
            )
            self.db.session.add(app)

        return app

    def get_app(self, app_id: uuid.UUID) -> App:
        return self.db.session.query(App).get(app_id)

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
