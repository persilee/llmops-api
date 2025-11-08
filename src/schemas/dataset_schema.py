from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import URL, DataRequired, Length, Optional

from pkg.paginator.paginator import PaginatorReq
from src.model.dataset import Dataset
from src.schemas.swag_schema import req_schema, resp_schema


@req_schema
class CreateDatasetReq(FlaskForm):
    """创建知识库请求表单类

    用于验证创建知识库时的请求参数，包含知识库名称、图标和描述信息
    """

    name = StringField(
        "name",
        validators=[
            DataRequired("知识库名字不能为空"),
            Length(max=100, message="知识库名字不能超过100个字符"),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("知识库图标不能为空"),
            URL("知识库图标必须是一个有效的URL"),
        ],
    )
    description = StringField(
        "description",
        default="",
        validators=[
            Optional(),
            Length(max=2000, message="知识库描述不能超过2000个字符"),
        ],
    )


@req_schema
class UpdateDatasetReq(FlaskForm):
    """更新知识库请求表单类

    用于验证更新知识库时的请求参数，包含数据集名称、图标和描述信息
    """

    name = StringField(
        "name",
        validators=[
            DataRequired("知识库名字不能为空"),
            Length(max=100, message="知识库名字不能超过100个字符"),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("知识库图标不能为空"),
            URL("知识库图标必须是一个有效的URL"),
        ],
    )
    description = StringField(
        "description",
        default="",
        validators=[
            Optional(),
            Length(max=2000, message="知识库描述不能超过2000个字符"),
        ],
    )


@resp_schema()
class GetDatasetResp(Schema):
    """获取知识库响应模式类

    用于序列化知识库数据，定义返回给客户端的数据结构
    """

    # 知识库唯一标识符
    id = fields.UUID(dump_default="")
    # 知识库名称
    name = fields.String(dump_default="")
    # 知识库图标URL
    icon = fields.String(dump_default="")
    # 知识库描述信息
    description = fields.String(dump_default="")
    # 知识库中的文档数量
    document_count = fields.Integer(dump_default=0)
    # 知识库被访问的次数
    hit_count = fields.Integer(dump_default=0)
    # 关联的应用数量
    related_app_count = fields.Integer(dump_default=0)
    # 知识库中字符总数
    character_count = fields.Integer(dump_default=0)
    # 最后更新时间（时间戳）
    updated_at = fields.Integer(dump_default=0)
    # 创建时间（时间戳）
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs: dict) -> dict:
        """预处理数据

        在序列化之前处理数据，将时间字段转换为时间戳格式

        Args:
            data: Dataset对象，包含知识库的原始数据
            **kwargs: 额外的关键字参数

        Returns:
            dict: 处理后的数据字典，包含所有需要序列化的字段

        """
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "hit_count": data.hit_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "updated_at": int(data.updated_at.timestamp()),
            "created_at": int(data.created_at.timestamp()),
        }


class GetDatasetsWithPageReq(PaginatorReq):
    """分页获取知识库列表的请求参数类

    继承自 PaginatorReq，包含分页相关的参数。
    添加了可选的搜索词字段，用于筛选数据集。
    """

    search_word = StringField("search_word", default="", validators=[Optional()])


@resp_schema()
class GetDatasetsWithPageResp(Schema):
    """获取知识库列表及分页响应模式类

    用于序列化知识库数据，定义返回给客户端的数据结构
    """

    # 知识库唯一标识符
    id = fields.UUID(dump_default="")
    # 知识库名称
    name = fields.String(dump_default="")
    # 知识库图标URL
    icon = fields.String(dump_default="")
    # 知识库描述信息
    description = fields.String(dump_default="")
    # 知识库中的文档数量
    document_count = fields.Integer(dump_default=0)
    # 关联的应用数量
    related_app_count = fields.Integer(dump_default=0)
    # 知识库中字符总数
    character_count = fields.Integer(dump_default=0)
    # 最后更新时间（时间戳）
    updated_at = fields.Integer(dump_default=0)
    # 创建时间（时间戳）
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs: dict) -> dict:
        """预处理数据

        在序列化之前处理数据，将时间字段转换为时间戳格式

        Args:
            data: Dataset对象，包含知识库的原始数据
            **kwargs: 额外的关键字参数

        Returns:
            dict: 处理后的数据字典，包含所有需要序列化的字段

        """
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "updated_at": int(data.updated_at.timestamp()),
            "created_at": int(data.created_at.timestamp()),
        }
