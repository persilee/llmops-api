import json
import logging
import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import (
    WorkflowConfig,
    WorkflowState,
)
from src.core.workflow.nodes import BaseNode
from src.core.workflow.utils.helper import extract_variables_from_state
from src.entity.workflow_entity import WorkflowStatus
from src.model import Workflow

from .iteration_entity import IterationNodeData

logger = logging.getLogger(__name__)


class IterationNode(BaseNode):
    """迭代节点"""

    node_data: IterationNodeData
    workflow: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """构造函数，完成数据的初始化"""
        try:
            # 1.调用父类构造函数完成数据初始化
            super().__init__(*args, **kwargs)

            # 2.判断是否传递的工作流id
            if len(self.node_data.workflow_ids) != 1:
                self.workflow = None
            else:
                # 3.导入依赖注入及相关服务
                from app.http.module import injector
                from pkg.sqlalchemy import SQLAlchemy

                db = injector.get(SQLAlchemy)
                workflow_record = db.session.query(Workflow).get(
                    self.node_data.workflow_ids[0],
                )

                # 4.判断工作流是否存在并且已发布
                if (
                    not workflow_record
                    or workflow_record.status != WorkflowStatus.PUBLISHED
                ):
                    self.workflow = None
                else:
                    # 5.已发布且存在，则构建工作流并存储
                    from src.core.workflow import Workflow as WorkflowTool

                    self.workflow = WorkflowTool(
                        workflow_config=WorkflowConfig(
                            account_id=workflow_record.account_id,
                            name="iteration_workflow",
                            description=self.node_data.description,
                            nodes=workflow_record.graph.get("nodes", []),
                            edges=workflow_record.graph.get("edges", []),
                        ),
                    )
        except Exception:
            # 6.出现异常则将工作流重置为空，使用相对宽松的校验范式
            logger.exception("迭代节点子工作流构建失败")

            self.workflow = None

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
    ) -> WorkflowState:
        """迭代节点调用函数，循环遍历将工作流的结果进行输出"""
        # 1.提取节点输入变量字典映射
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)
        inputs = inputs_dict.get("inputs", [])

        # 2.异常检测，涵盖工作流不存在、工作流输入参数不唯一、数据为非列表、长度为0等
        if (
            self.workflow is None
            or len(self.workflow.args) != 1
            or not isinstance(inputs, list)
            or len(inputs) == 0
        ):
            return {
                "node_results": [
                    NodeResult(
                        node_data=self.node_data,
                        status=NodeStatus.FAILED,
                        inputs=inputs_dict,
                        outputs={"outputs": []},
                        latency=(time.perf_counter() - start_at),
                    ),
                ],
            }

        # 3.获取工作流的输入字段结构
        param_key = next(iter(self.workflow.args.keys()))

        # 4.工作流+数据均存在，则循环遍历输入数据调用迭代工作流获取结果
        outputs = []
        for item in inputs:
            # 5.构建输入字典信息
            data = {param_key: item}

            # 6.调用工作流获取结果，这里可以修改为并行执行提升效率，
            # 得到的结构转换成字符串
            iteration_result = self.workflow.invoke(data)
            outputs.append(json.dumps(iteration_result, ensure_ascii=False))

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs={"outputs": outputs},
                    latency=(time.perf_counter() - start_at),
                ),
            ],
        }
