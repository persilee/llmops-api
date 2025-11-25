from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import FloatField, IntegerField, StringField
from wtforms.validators import URL, AnyOf, DataRequired, Length, NumberRange, Optional

from pkg.paginator.paginator import PaginatorReq
from src.entity.dataset_entity import RetrievalStrategy
from src.lib.helper import datetime_to_timestamp
from src.model.dataset import Dataset, DatasetQuery
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


@req_schema
class HitReq(FlaskForm):
    """知识库召回测试请求"""

    query = StringField(
        "query",
        validators=[
            DataRequired("查询语句不能为空"),
            Length(max=200, message="查询语句的最大长度不能超过200"),
        ],
    )
    retrieval_strategy = StringField(
        "retrieval_strategy",
        validators=[
            DataRequired("检索策略不能为空"),
            AnyOf(
                [item.value for item in RetrievalStrategy],
                message="检索策略格式错误",
            ),
        ],
    )
    k = IntegerField(
        "k",
        validators=[
            DataRequired("最大召回数量不能为空"),
            NumberRange(min=1, max=10, message="最大召回数量的范围在1-10"),
        ],
    )
    score = FloatField(
        "score",
        validators=[NumberRange(min=0, max=0.99, message="最小匹配度范围在0-0.99")],
    )


@resp_schema()
class GetDatasetQueriesResp(Schema):
    """获取知识库最近查询响应结构"""

    id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    source = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: DatasetQuery, **kwargs: dict) -> dict:
        return {
            "id": data.id,
            "dataset_id": data.dataset_id,
            "query": data.query,
            "source": data.source,
            "created_at": datetime_to_timestamp(data.created_at),
        }
