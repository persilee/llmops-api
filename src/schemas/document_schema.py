import uuid

from flask_wtf import FlaskForm
from marshmallow import Schema, ValidationError, fields, pre_dump
from wtforms import StringField
from wtforms.validators import AnyOf, DataRequired

from src.entity.dataset_entity import DEFAULT_PROCESS_RULE, ProcessType
from src.model.dataset import Document
from src.schemas.schema import DictField, ListField
from src.schemas.swag_schema import req_schema, resp_schema

MAX_UPLOAD_FILES = 10
EXPECTED_PRE_PROCESS_RULES_COUNT = 2
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 1000


@req_schema
class CreateDocumentReq(FlaskForm):
    """文档创建请求模式类

    用于定义文档创建接口的请求数据结构，包含以下字段：
    - upload_file_ids: 上传文件ID列表
    - process_type: 文档处理类型（自动/自定义）
    - rule: 文档处理规则配置

    主要功能：
    1. 验证上传文件ID列表的合法性
    2. 验证文档处理类型
    3. 验证文档处理规则，包括：
       - 预处理规则验证
       - 分段规则验证
    4. 根据处理类型应用相应的规则配置
    """

    upload_file_ids = ListField("upload_file_ids")
    process_type = StringField(
        "process_type",
        validators=[
            DataRequired("文档处理类型不能为空"),
            AnyOf(
                values=[ProcessType.AUTOMATIC, ProcessType.CUSTOM],
                message="文档处理类型不合法",
            ),
        ],
    )
    rule = DictField("rule")

    def validate_upload_file_ids(self, field: ListField) -> None:
        """验证上传文件ID列表的合法性

        Args:
            field: ListField对象，包含待验证的文件ID列表

        Raises:
            ValidationError: 当出现以下情况时抛出异常：
                - 输入不是列表格式
                - 列表长度为0或超过最大限制(MAX_UPLOAD_FILES=10)
                - 列表中包含无效的UUID格式ID

        """
        # 验证输入是否为列表格式
        if not isinstance(field.data, list):
            error_msg = "上传文件id列表格式不正确"
            raise ValidationError(error_msg)

        # 验证列表长度是否合法
        if len(field.data) == 0 or len(field.data) > MAX_UPLOAD_FILES:
            error_msg = "上传文件id列表长度不合法"
            raise ValidationError(error_msg)

        # 验证每个ID是否为有效的UUID格式
        for upload_file_id in field.data:
            try:
                uuid.UUID(upload_file_id)
            except ValueError as e:
                error_msg = "上传文件id列表中存在不合法的id"
                raise ValidationError(error_msg) from e

        # 去除列表中的重复项，保持原始顺序
        field.data = list(dict.fromkeys(field.data))

    def _validate_pre_process_rules(self, rules: dict) -> None:
        # 验证pre_process_rules字段是否存在且为列表类型
        if "pre_process_rules" not in rules or not isinstance(
            rules["pre_process_rules"],
            list,
        ):
            error_msg = "pre_process_rules字段格式不正确"
            raise ValidationError(error_msg)

        # 创建字典用于存储唯一的预处理规则
        unique_pre_process_rule_dict = {}
        # 遍历每个预处理规则
        for pre_process_rule in rules["pre_process_rules"]:
            # 验证规则id是否存在且为合法值
            if "id" not in pre_process_rule or pre_process_rule["id"] not in [
                "remove_extra_space",  # 移除多余空格
                "remove_url_and_email",  # 移除URL和邮箱
            ]:
                error_msg = "pre_process_rules字段中存在不合法的id"
                raise ValidationError(error_msg)
            # 验证enabled字段是否存在且为布尔类型
            if "enabled" not in pre_process_rule or not isinstance(
                pre_process_rule["enabled"],
                bool,
            ):
                error_msg = "pre_process_rules字段中存在不合法的enabled"
                raise ValidationError(error_msg)

            # 将规则存入字典，确保id的唯一性
            unique_pre_process_rule_dict[pre_process_rule["id"]] = {
                "id": pre_process_rule["id"],
                "enabled": pre_process_rule["enabled"],
            }

        # 验证预处理规则数量是否符合预期（必须包含两个不同的规则）
        if len(unique_pre_process_rule_dict) != EXPECTED_PRE_PROCESS_RULES_COUNT:
            error_msg = "pre_process_rules字段中存在重复的id"
            raise ValidationError(error_msg)

    def _validate_segment_rules(self, segment: dict) -> None:
        # 验证separators字段是否存在且为列表类型
        if "separators" not in segment or not isinstance(segment["separators"], list):
            error_msg = "segment字段中不存在separators字段或separators字段不是list类型"
            raise ValidationError(error_msg)

        # 验证separators列表中的每个元素都是字符串类型
        for separator in segment["separators"]:
            if not isinstance(separator, str):
                error_msg = "segment字段中separators字段存在非字符串类型"
                raise ValidationError(error_msg)

        # 验证separators列表不能为空
        if len(segment["separators"]) == 0:
            error_msg = "segment字段中separators字段为空"
            raise ValidationError(error_msg)

        # 验证chunk_size字段是否存在且为整数类型
        if "chunk_size" not in segment or not isinstance(segment["chunk_size"], int):
            error_msg = "segment字段中不存在chunk_size字段或chunk_size字段不是int类型"
            raise ValidationError(error_msg)

        # 验证chunk_size的值在MIN_CHUNK_SIZE和MAX_CHUNK_SIZE之间（100-1000）
        if (
            segment["chunk_size"] < MIN_CHUNK_SIZE
            or segment["chunk_size"] > MAX_CHUNK_SIZE
        ):
            error_msg = "segment字段中chunk_size字段不在100到1000之间"
            raise ValidationError(error_msg)

        # 验证chunk_overlap字段是否存在且为整数类型
        if "chunk_overlap" not in segment or not isinstance(
            segment["chunk_overlap"],
            int,
        ):
            error_msg = (
                "segment字段中不存在chunk_overlap字段或chunk_overlap字段不是int类型"
            )
            raise ValidationError(error_msg)

        # 验证chunk_overlap的值在0到chunk_size的一半之间
        if not (0 < segment["chunk_overlap"] < segment["chunk_size"] * 0.5):
            error_msg = (
                f"segment字段中chunk_overlap字段不在0到"
                f"{segment['chunk_size'] * 0.5}之间"
            )
            raise ValidationError(error_msg)

    def validate_rule(self, field: DictField) -> None:
        """验证文档处理规则。

        根据处理类型(自动/自定义)验证规则的有效性：
        1. 如果是自动处理类型，使用默认处理规则
        2. 如果是自定义处理类型，验证规则的完整性和有效性：
           - 验证预处理规则(_validate_pre_process_rules)：
             * 检查规则是否为列表类型
             * 确保包含两个不同的预处理规则
             * 验证规则的有效性
           - 验证分段规则(_validate_segment_rules)：
             * 检查分隔符是否为非空字符串列表
             * 验证分块大小是否在有效范围内(100-1000)
             * 确保分块重叠不超过分块大小的一半

        Args:
            field (DictField): 包含处理规则的字段对象

        Raises:
            ValidationError: 当规则格式不正确、缺少必要字段或字段值无效时抛出

        Returns:
            None

        """
        # 如果处理类型为自动，使用默认处理规则
        if self.process_type.data == ProcessType.AUTOMATIC:
            field.data = DEFAULT_PROCESS_RULE["rule"]
            return

        # 验证自定义规则是否为非空字典
        if not isinstance(field.data, dict) or len(field.data) == 0:
            error_msg = "自定义处理规则格式不正确"
            raise ValidationError(error_msg)

        # 验证预处理规则
        self._validate_pre_process_rules(field.data)

        # 验证segment字段是否存在且为字典类型
        if "segment" not in field.data or not isinstance(field.data["segment"], dict):
            error_msg = "segment字段不存在或不是dict类型"
            raise ValidationError(error_msg)

        # 验证分段规则
        self._validate_segment_rules(field.data["segment"])

        # 格式化规则数据，只保留必要的字段
        field.data = {
            "pre_process_rules": field.data["pre_process_rules"],
            "segment": {
                "separators": field.data["segment"]["separators"],
                "chunk_size": field.data["segment"]["chunk_size"],
                "chunk_overlap": field.data["segment"]["chunk_overlap"],
            },
        }


@resp_schema()
class CreateDocumentResp(Schema):
    """文档创建响应模式类

    用于定义文档创建接口的响应数据结构，包含文档列表和批次号信息
    """

    # 文档列表字段，默认为空列表
    documents = fields.List(fields.Dict, dump_default=[])
    # 批次号字段，默认为空字符串
    batch = fields.String(dump_default="")

    @pre_dump
    def process_data(self, data: tuple[list[Document], str], **kwargs: dict) -> dict:
        """处理响应数据的方法

        Args:
            data: 包含文档列表和批次号的元组
                - data[0]: Document对象列表
                - data[1]: 批次号字符串
            **kwargs: 额外的关键字参数

        Returns:
            dict: 格式化后的响应数据，包含：
                - documents: 文档信息列表，每个文档包含id、name、status和created_at
                - batch: 批次号字符串

        """
        return {
            "documents": [
                {
                    "id": document.id,
                    "name": document.name,
                    "status": document.status,
                    "created_at": int(document.created_at.timestamp()),
                }
                for document in data[0]
            ],
            "batch": data[1],
        }
