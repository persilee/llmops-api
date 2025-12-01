from dataclasses import dataclass
from uuid import UUID

from injector import inject

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy
from src.model.account import Account
from src.service.base_service import BaseService


@inject
@dataclass
class AccountService(BaseService):
    db: SQLAlchemy

    def get_account(self, account_id: UUID) -> Account:
        return self.get(Account, account_id )
