from typing import Any

from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from pydantic import PrivateAttr, json

from src.core.tools.api_tool.entities.tool_entity import ToolEntity
from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.tool.tool_entity import ToolNodeData
from src.core.workflow.utils.helper import extract_variables_from_state
from src.exception.exception import FailException, NotFoundException
from src.model.api_tool import ApiTool


class ToolNode(BaseNode):
    """扩展插件节点"""

    node_data: ToolNodeData
    _tool: BaseTool = PrivateAttr(None)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """构造函数，完成对内置工具的初始化"""
        # 1.调用父类构造函数完成数据初始化
        super().__init__(*args, **kwargs)

        # 2.导入依赖注入及工具提供者
        from app.http.module import injector

        # 3.判断是内置插件还是API插件，执行不同的操作
        if self.node_data.tool_type == "builtin_tool":
            from src.core.tools.builtin_tools.providers import BuiltinProviderManager

            builtin_provider_manager = injector.get(BuiltinProviderManager)

            # 4.调用内置提供者获取内置插件
            _tool = builtin_provider_manager.get_tool(
                self.node_data.provider_id,
                self.node_data.tool_id,
            )
            if not _tool:
                error_msg = "该内置插件扩展不存在，请核实后重试"
                raise NotFoundException(error_msg)

            self._tool = _tool(**self.node_data.params)
        else:
            # 5.API插件，调用数据库查询记录并创建API插件
            from pkg.sqlalchemy import SQLAlchemy

            db = injector.get(SQLAlchemy)

            # 6.根据传递的提供者名字+工具名字查询工具
            api_tool = (
                db.session.query(ApiTool)
                .filter(
                    ApiTool.provider_id == self.node_data.provider_id,
                    ApiTool.name == self.node_data.tool_id,
                )
                .one_or_none()
            )
            if not api_tool:
                error_msg = "该API扩展插件不存在，请核实重试"
                raise NotFoundException(error_msg)

            # 7.导入API插件提供者

            from src.core.tools.providers.api_provider_manager import ApiProviderManager

            api_provider_manager = injector.get(ApiProviderManager)

            # 8.创建API工具提供者并赋值
            self._tool = api_provider_manager.get_tool(
                ToolEntity(
                    id=str(api_tool.id),
                    name=api_tool.name,
                    url=api_tool.url,
                    method=api_tool.method,
                    description=api_tool.description,
                    headers=api_tool.provider.headers,
                    parameters=api_tool.parameters,
                ),
            )

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
    ) -> WorkflowState:
        """扩展插件执行节点，根据传递的信息调用预设的插件，涵盖内置插件及API插件"""
        # 1.提取节点中的输入数据
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2.调用插件并获取结果
        try:
            result = self._tool.invoke(inputs_dict)
        except Exception as e:
            error_msg = "扩展插件执行失败，请稍后尝试"
            raise FailException(error_msg) from e

        # 3.检测result是否为字符串，如果不是则转换
        if not isinstance(result, str):
            # 3.1[升级更新] 避免汉字被转义
            result = json.dumps(result, ensure_ascii=False)

        # 4.提取并构建输出数据结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = result
        else:
            outputs["text"] = result

        # 5.构建响应状态并返回
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                ),
            ],
        }
