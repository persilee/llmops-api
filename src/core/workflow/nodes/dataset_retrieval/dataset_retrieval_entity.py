from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.core.workflow.entities.node_entity import BaseNodeData
from src.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableType,
    VariableValueType,
)
from src.entity.dataset_entity import RetrievalStrategy
from src.exception.exception import FailException


class RetrievalConfig(BaseModel):
    """检索配置类

    用于配置知识库检索的相关参数，包括检索策略、返回结果数量和相似度阈值
    """

    # 检索策略，默认使用语义检索
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC
    # 返回结果的最大数量，默认返回5个最相关的结果
    k: int = 5
    # 相似度阈值，默认为0表示不限制最低相似度
    score: float = 0


class DatasetRetrievalNodeData(BaseNodeData):
    """知识库检索节点数据类

    用于定义知识库检索节点的配置参数，包括知识库ID、检索策略、输入输出变量等
    """

    # 知识库ID列表，用于指定要检索的知识库
    dataset_ids: list[UUID]
    # 检索配置，包含检索策略、返回结果数量k和相似度阈值score
    retrieval_config: RetrievalConfig = RetrievalConfig()
    # 输入变量列表，默认为空列表
    inputs: list[VariableEntity] = Field(default_factory=list)
    # 输出变量列表，默认包含一个名为combine_documents的生成类型变量
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(
                name="combine_documents",
                value={"type": VariableValueType.GENERATED},
            ),
        ],
    )

    @classmethod
    @field_validator("inputs")
    def validate_inputs(cls, value: list[VariableEntity]) -> list[VariableEntity]:
        """验证知识库检索节点的输入参数

        Args:
            value: 输入变量列表

        Returns:
            list[VariableEntity]: 验证通过的输入变量列表

        Raises:
            FailException: 当输入参数不符合要求时抛出异常

        """
        # 检查输入参数数量是否为1
        if len(value) != 1:
            error_msg = "知识库检索节点只接受一个输入"
            raise FailException(error_msg)

        # 获取唯一的输入参数
        query_input: VariableEntity = value[0]
        # 验证输入参数的名称、类型和必需性
        if (
            query_input.name != "query"
            or query_input.type != VariableType.STRING
            or query_input.required is False
        ):
            error_msg = "知识库检索节点只接受一个名为query的字符串类型输入"
            raise FailException(error_msg)

        return value
