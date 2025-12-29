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
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC
    k: int = 5
    score: float = 0


class DatasetRetrievalNodeData(BaseNodeData):
    dataset_ids: list[UUID]
    retrieval_config: RetrievalConfig = RetrievalConfig()
    inputs: list[VariableEntity] = Field(default_factory=list)
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
        if len(value) != 1:
            error_msg = "知识库检索节点只接受一个输入"
            raise FailException(error_msg)

        query_input: VariableEntity = value[0]
        if (
            query_input.name != "query"
            or query_input.type != VariableType.STRING
            or query_input.required is False
        ):
            error_msg = "知识库检索节点只接受一个名为query的字符串类型输入"
            raise FailException(error_msg)

        return value
