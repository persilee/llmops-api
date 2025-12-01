import os
from dataclasses import dataclass
from typing import Any

import jwt
from injector import inject


@inject
@dataclass
class JwtService:
    @classmethod
    def generate_token(cls, payload: dict[str, Any]) -> str:
        """生成JWT令牌

        Args:
            payload (dict[str, Any]): 要编码到JWT中的数据载荷

        Returns:
            str: 生成的JWT令牌字符串

        """
        secret_key = os.getenv("JWT_SECRET_KEY")

        return jwt.encode(payload, secret_key, algorithm="HS256")

    @classmethod
    def decode_token(cls, token: str) -> dict[str, Any]:
        """解码JWT令牌

        Args:
            token (str): 要解码的JWT令牌字符串

        Returns:
            dict[str, Any]: 解码后的令牌载荷数据

        Raises:
            ValueError: 当令牌过期或无效时抛出，包含具体的错误信息
            Exception: 其他解码过程中可能出现的异常

        """
        secret_key = os.getenv("JWT_SECRET_KEY")

        try:
            return jwt.decode(token, secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as e:
            error_msg = "授权认证已过期，请重新登录"
            raise ValueError(error_msg) from e
        except jwt.InvalidTokenError as e:
            error_msg = "授权认证无效，请重新登录"
            raise ValueError(error_msg) from e
        except Exception:
            raise
