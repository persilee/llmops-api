import math
from dataclasses import dataclass
from typing import Any

from flask_wtf import FlaskForm
from wtforms import IntegerField
from wtforms.validators import NumberRange, Optional

from pkg.sqlalchemy.sqlalchemy import SQLAlchemy


class PaginatorReq(FlaskForm):
    """分页请求表单类

    用于接收和验证分页相关的请求参数
    """

    current_page = IntegerField(
        "current_page",
        default=1,
        validators=[
            Optional(),
            NumberRange(min=1, max=9999, message="页数范围在1-9999之间"),
        ],
        description="当前页码，默认为第1页，取值范围1-9999",
    )
    page_size = IntegerField(
        "page_size",
        default=20,
        validators=[
            Optional(),
            NumberRange(min=1, max=50, message="每页记录数范围在1-50之间"),
        ],
        description="每页显示的记录数，默认为20条，取值范围1-50",
    )


@dataclass
class Paginator:
    """分页器类

    用于处理数据库查询的分页逻辑，包含当前页码、每页记录数、总记录数和总页数等信息
    """

    current_page: int = 1  # 当前页码，默认为第1页
    page_size: int = 20  # 每页显示的记录数，默认为20条
    total_record: int = 0  # 总记录数
    total_page: int = 0  # 总页数

    def __init__(self, db: SQLAlchemy, req: PaginatorReq = None) -> None:
        """初始化分页器

        Args:
            db: SQLAlchemy数据库实例
            req: PaginatorReq分页请求表单对象，包含current_page和page_size参数

        """
        if req is not None:
            self.current_page = req.current_page.data
            self.page_size = req.page_size.data
        self.db = db

    def paginate(self, select) -> list[Any]:
        """执行分页查询

        Args:
            select: SQLAlchemy查询对象

        Returns:
            list[Any]: 当前页的数据列表

        Raises:
            404错误：当页码超出范围时抛出

        """
        p = self.db.paginate(
            select,
            page=self.current_page,
            per_page=self.page_size,
            error_out=False,
        )

        self.total_record = p.total
        self.total_page = math.ceil(p.total / self.page_size)

        return p.items


@dataclass
class PageModel:
    """分页结果模型类

    用于封装分页查询的结果，包含数据列表和分页器信息

    Attributes:
        list: 当前页的数据列表
        paginator: 分页器对象，包含分页相关信息

    """

    list: list[Any]
    paginator: Paginator
