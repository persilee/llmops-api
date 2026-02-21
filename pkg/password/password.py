import base64
import binascii
import hashlib
import re
from typing import Any

# 密码格式验证的正则表达式
# 要求：
# 1. 必须包含至少一个字母（a-zA-Z）
# 2. 必须包含至少一个数字（\d）
# 3. 长度必须在8到16个字符之间
# 4. 可以包含其他任意字符
AUTH_CREDENTIAL_FORMAT = r"^(?=.*[a-zA-Z])(?=.*\d).{8,16}$"



def validate_password(
    password: str,
    pattern: str = AUTH_CREDENTIAL_FORMAT,
) -> bool:
    """验证密码是否符合要求

    Args:
        password (str): 待验证的密码字符串
        pattern (str): 密码验证的正则表达式模式，默认使用预定义的password_pattern

    Returns:
        bool: 密码验证通过返回True

    Raises:
        ValueError: 当密码不符合要求时抛出异常

    """
    # 使用正则表达式匹配密码
    if re.match(pattern, password) is None:
        # 设置错误提示信息
        error_msg = "密码必须包含字母和数字，长度在8到16之间"
        # 抛出验证失败的异常
        raise ValueError(error_msg)

    return True


def hash_password(password: str, salt: Any) -> bytes:
    """使用PBKDF2-HMAC-SHA256算法对密码进行哈希处理

    Args:
        password (str): 需要哈希处理的原始密码
        salt (Any): 用于增加密码安全性的盐值，可以是任意类型

    Returns:
        bytes: 返回经过十六进制编码的哈希值

    Note:
        - 使用PBKDF2算法进行10000次迭代以增加安全性
        - 使用SHA256作为哈希函数
        - 返回值为十六进制编码的字节串

    """
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 10000)

    return binascii.hexlify(dk)


def compare_password(
    password: str,
    password_hashed_base64: Any,
    salt_base64: Any,
) -> bool:
    """比较密码是否匹配

    Args:
        password (str): 待验证的原始密码
        password_hashed_base64 (Any): 经过base64编码的哈希密码
        salt_base64 (Any): 经过base64编码的盐值

    Returns:
        bool: 密码匹配返回True，不匹配返回False

    Note:
        - 使用PBKDF2-HMAC-SHA256算法进行密码验证
        - 函数会自动解码base64编码的哈希值和盐值
        - 使用相同的哈希算法和参数进行比较

    """
    return hash_password(password, base64.b64decode(salt_base64)) == base64.b64decode(
        password_hashed_base64,
    )
