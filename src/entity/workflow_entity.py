from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流状态类型枚举"""

    DRAFT = "draft"
    PUBLISHED = "published"


class WorkflowResultStatus(str, Enum):
    """工作流运行结果状态"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# 工作流默认配置信息，默认添加一个空的工作流
DEFAULT_WORKFLOW_CONFIG = {
    "graph": {},
    "draft_graph": {
        "nodes": [],
        "edges": [],
    },
}

DEFAULT_DRAFT_GRAPH = {
    "edges": [],
    "nodes": [
        {
            "id": "9d1fdcb7-ad1f-4b5c-b26a-33042091c27b",
            "title": "开始节点",
            "inputs": [],
            "position": {"x": 180.0, "y": 93.0},
            "node_type": "start",
            "description": "工作流的起点节点，支持定义工作流的起点输入等信息",
        },
        {
            "id": "dc5d2a83-77fc-422e-98d2-1526375c0761",
            "title": "结束节点",
            "outputs": [],
            "position": {"x": 795.0, "y": 119.0},
            "node_type": "end",
            "description": "工作流的结束节点，支持定义工作流最终输出的变量等信息",
        },
    ],
}
