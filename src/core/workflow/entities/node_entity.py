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
    """节点状态枚举

    用于表示工作流中节点的执行状态
    """

    RUNNING = "running"  # 运行中
    SUCCEEDED = "succeeded"  # 执行成功
    FAILED = "failed"  # 执行失败


class NodeResult(BaseModel):
    """节点执行结果模型

    用于存储工作流中节点的执行结果，包括节点数据、状态、输入输出等信息
    """

    node_data: BaseNodeData  # 节点的基础数据信息
    status: NodeStatus = NodeStatus.RUNNING  # 节点执行状态，默认为运行中
    inputs: dict[str, Any] = Field(default_factory=dict)  # 节点输入数据字典
    outputs: dict[str, Any] = Field(default_factory=dict)  # 节点输出数据字典
    latency: float = 0.0  # 节点执行延迟时间（秒）
    error: str = ""  # 节点执行错误信息，若无错误则为空字符串
