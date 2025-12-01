from .database_extension import db
from .login_extension import login_manager
from .migrate_extension import migrate
from .redis_extension import redis_client
from .swagger_extension import swag

__all__ = ["db", "login_manager", "migrate", "redis_client", "swag"]
