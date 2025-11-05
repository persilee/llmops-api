from dataclasses import dataclass

from injector import inject

from pkg.sqlalchemy import SQLAlchemy
from src.model.upload_file import UploadFile
from src.service.base_service import BaseService


@inject
@dataclass
class UploadFileService(BaseService):
    db: SQLAlchemy

    def create_upload_file(self, **kwargs: dict) -> UploadFile:
        return self.create(UploadFile, **kwargs)

    def get_upload_file_by_hash(self, upload_file_hash: str) -> UploadFile | None:
        return (
            self.db.session.query(UploadFile)
            .filter_by(
                hash=upload_file_hash,
            )
            .first()
        )
