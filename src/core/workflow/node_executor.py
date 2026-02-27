from collections.abc import Iterator
from typing import Any

from flask import current_app
from langchain_core.runnables import RunnableConfig

from src.core.workflow.entities.node_entity import NodeStatus, NodeType
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.workflow import NodeClasses


class NodeExecutor:
    """单个节点执行器类，用于执行工作流中的单个节点。

    该类负责：
    1. 管理单个节点的配置
    2. 创建和执行节点实例
    3. 处理节点的输入输出

    Attributes:
        _node_config: 节点配置对象
        _account_id: 账户ID
        _node: 节点实例

    """

    def __init__(self, node_config: dict, account_id: str) -> None:
        """初始化节点执行器

        Args:
            node_config: 节点配置字典
            account_id: 账户ID

        """
        self._node_config = node_config
        self._account_id = account_id
        self._node = self._create_node()

    def _create_node(self) -> Any:
        """创建节点实例

        Returns:
            Any: 创建的节点实例

        Raises:
            ValueError: 当节点类型不存在时抛出异常

        """
        # 获取节点类型
        node_type = self._node_config.get("node_type")

        # 定义节点创建器字典
        node_creators = {
            # 开始节点创建器
            NodeType.START: lambda: NodeClasses[NodeType.START](
                node_data=self._node_config,
            ),
            # LLM节点创建器
            NodeType.LLM: lambda: NodeClasses[NodeType.LLM](
                node_data=self._node_config,
            ),
            # 模板转换节点创建器
            NodeType.TEMPLATE_TRANSFORM: lambda: NodeClasses[
                NodeType.TEMPLATE_TRANSFORM
            ](
                node_data=self._node_config,
            ),
            # 数据集检索节点创建器，需要额外的flask应用和账户ID参数
            NodeType.DATASET_RETRIEVAL: lambda: NodeClasses[NodeType.DATASET_RETRIEVAL](
                flask_app=current_app._get_current_object(),  # noqa: SLF001
                account_id=self._account_id,
                node_data=self._node_config,
            ),
            # 代码节点创建器
            NodeType.CODE: lambda: NodeClasses[NodeType.CODE](
                node_data=self._node_config,
            ),
            # 工具节点创建器
            NodeType.TOOL: lambda: NodeClasses[NodeType.TOOL](
                node_data=self._node_config,
            ),
            # HTTP请求节点创建器
            NodeType.HTTP_REQUEST: lambda: NodeClasses[NodeType.HTTP_REQUEST](
                node_data=self._node_config,
            ),
            # 结束节点创建器
            NodeType.END: lambda: NodeClasses[NodeType.END](
                node_data=self._node_config,
            ),
        }

        # 获取对应节点类型的创建器
        creator = node_creators.get(node_type)
        if creator is None:
            error_msg = f"节点类型 {node_type} 不存在"
            raise ValueError(error_msg)

        return creator()

    def stream(
        self,
        input_data: dict[str, Any],
        config: RunnableConfig | None = None,
        **kwargs: Any | None,
    ) -> Iterator[dict[str, Any]]:
        """流式执行单个节点

        Args:
            input_data: 输入数据字典
            config: 可选的运行配置
            **kwargs: 其他可选参数

        Returns:
            Iterator[dict[str, Any]]: 流式返回节点执行结果

        """
        node_id = self._node_config.get("id")

        # 创建工作流状态
        state = WorkflowState(
            inputs=input_data,
            node_results=[],
            is_node=True,
        )

        try:
            # 执行节点
            result = self._node.invoke(state)

            # 格式化输出
            output = {
                node_id: {
                    "node_results": [result],
                },
            }
            yield output

        except (ValueError, RuntimeError) as e:
            # 处理错误情况
            error_result = {
                "status": NodeStatus.FAILED,
                "error": str(e),
            }
            output = {
                node_id: {
                    "node_results": [error_result],
                },
            }
            yield output
