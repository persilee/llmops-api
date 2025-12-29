from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """节点类型枚举"""

    START = "start"
    LLM = "llm"
    TOOL = "tool"
    CODE = "code"
    DATASET_RETRIEVAL = "dataset_retrieval"
    HTTP_REQUEST = "http_request"
    TEMPLATE_TRANSFORM = "template_transform"
    # 新增意图识别分类节点
    QUESTION_CLASSIFIER = "question_classifier"
    # 新增迭代节点
    ITERATION = "iteration"
    END = "end"


class BaseNodeData(BaseModel):
    class Position(BaseModel):
        """节点坐标基础模型"""

        x: float = 0
        y: float = 0

    class Config:
        allow_population_by_field_name = True  # 允许通过字段名进行赋值

    id: UUID
    title: str = ""
    node_type: NodeType
    description: str = ""
    position: Position = Field(
        default_factory=lambda: {"x": 0, "y": 0},
    )  # 节点对应的坐标信息


class NodeStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeResult(BaseModel):
    node_data: BaseNodeData
    status: NodeStatus = NodeStatus.RUNNING
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
