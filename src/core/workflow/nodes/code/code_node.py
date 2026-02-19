import ast
import json
import time
from typing import Any, ClassVar

import requests
from langchain_core.runnables import RunnableConfig

from src.core.workflow.entities.node_entity import NodeResult, NodeStatus
from src.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.base_node import BaseNode
from src.core.workflow.nodes.code.code_entity import CodeNodeData
from src.core.workflow.utils.helper import extract_variables_from_state
from src.exception.exception import FailException


class SafeCodeExecutor:
    """安全的代码执行器"""

    ALLOWED_BUILTINS: ClassVar[dict[str, Any]] = {
        "print": print,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
    }

    @classmethod
    def _raise_error(cls, error_msg: str) -> None:
        """抛出 FailException 异常的内部方法"""
        raise FailException(error_msg)

    @classmethod
    def execute(cls, code: str, *args: Any, **kwargs: Any) -> Any:
        """安全执行代码

        Args:
            code: 要执行的Python代码字符串
            *args: 传递给main函数的位置参数
            **kwargs: 传递给main函数的关键字参数

        Returns:
            Any: main函数的执行结果

        Raises:
            FailException:当代码不符合安全要求或执行出错时抛出

        """
        try:
            # 使用ast模块解析代码字符串为抽象语法树
            tree = ast.parse(code)

            main_func = None
            # 遍历语法树的所有节点，查找main函数定义
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    # 检查是否为main函数
                    if node.name == "main":
                        # 确保只有一个main函数
                        if main_func:
                            error_msg = "代码只能包含一个名为main的函数"
                            cls._raise_error(error_msg)
                        # 验证main函数的参数要求：必须只有一个名为params的参数
                        if (
                            len(node.args.args) != 1
                            or node.args.args[0].arg != "params"
                        ):
                            error_msg = "main函数必须只有一个参数，且参数名为params"
                            cls._raise_error(error_msg)
                        main_func = node
                    else:
                        # 如果函数名不是main，报错
                        error_msg = "代码必须包含一个名为main的函数"
                        cls._raise_error(error_msg)
                else:
                    # 如果不是函数定义，报错
                    error_msg = "代码必须包含一个函数"
                    cls._raise_error(error_msg)
            # 确保找到了main函数
            if not main_func:
                error_msg = "代码必须包含一个名为main的函数"
                cls._raise_error(error_msg)

            # 将语法树编译为可执行代码对象
            compiled_code = compile(tree, filename="<ast>", mode="exec")

            # 创建受限的全局命名空间，只包含允许的内置函数
            safe_globals = {
                "__builtins__": cls.ALLOWED_BUILTINS,
            }
            # 创建局部命名空间用于存储执行结果
            local_vars = {}

            # 在受限环境中执行编译后的代码
            exec(compiled_code, safe_globals, local_vars)  # noqa: S102

            # 检查main函数是否存在且可调用，并执行它
            if "main" in local_vars and callable(local_vars["main"]):
                return local_vars["main"](*args, **kwargs)

            # 如果没有找到可执行的main函数，报错
            error_msg = "代码必须包含一个名为main的函数"
            cls._raise_error(error_msg)

        except (SyntaxError, ValueError):
            # 捕获语法错误和值错误，转换为自定义异常
            cls._raise_error(error_msg)


class CodeNode(BaseNode):
    """代码执行节点，用于在工作流中执行Python代码。

    该节点可以：
    - 从工作流状态中提取输入变量
    - 执行用户提供的Python代码
    - 将执行结果映射到指定的输出变量
    - 更新工作流状态

    Attributes:
        node_data (CodeNodeData): 包含节点配置信息的数据类

    """

    node_data: CodeNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> WorkflowState:
        """执行代码节点并更新工作流状态。

        Args:
            state: WorkflowState对象，包含当前工作流的执行上下文和状态信息
            config: 可选的RunnableConfig配置对象，用于控制执行行为
            **kwargs: 额外的关键字参数，用于扩展功能

        Returns:
            WorkflowState: 更新后的工作流状态，包含节点执行结果

        Raises:
            FailException: 当代码执行结果不是字典类型时抛出异常

        执行流程：
            1. 从工作流状态中提取当前节点所需的输入变量
            2. 执行Python代码，传入提取的输入参数
            3. 验证代码执行结果是否为字典类型
            4. 初始化输出字典，用于存储节点执行结果
            5. 遍历所有输出变量，从执行结果中提取对应的值
            6. 构建并返回更新后的工作流状态

        """
        # 记录开始时间
        start_at = time.perf_counter()
        # 从工作流状态中提取当前节点所需的输入变量
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 执行Python代码，传入提取的输入参数
        result = self._execute_function(
            self.node_data.code,
            self.node_data.language,
            params=inputs_dict,
        )

        # 验证代码执行结果是否为字典类型
        if not isinstance(result, dict):
            self._raise_error("CodeNode 返回值必须为字典")

        # 初始化输出字典，用于存储节点执行结果
        outputs_dict = {}
        outputs = self.node_data.outputs  # 获取节点定义的输出变量列表
        # 遍历所有输出变量，从执行结果中提取对应的值
        for output in outputs:
            outputs_dict[output.name] = result.get(
                output.name,  # 尝试获取输出变量名对应的值
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(
                    output.type,
                ),  # 如果不存在，使用该类型的默认值
            )

        # 构建并返回更新后的工作流状态
        return {
            "node_results": [  # 节点执行结果列表
                NodeResult(
                    node_data=self.node_data,  # 节点数据
                    status=NodeStatus.SUCCEEDED,  # 执行状态为成功
                    inputs=inputs_dict,  # 节点输入
                    outputs=outputs_dict,  # 节点输出
                    latency=(time.perf_counter() - start_at),  # 执行耗时
                ),
            ],
        }

    @classmethod
    def _raise_error(cls, error_msg: str) -> None:
        """抛出 FailException 异常的内部方法"""
        raise FailException(error_msg)

    @classmethod
    def _execute_function(
        cls,
        code: str,
        language: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """执行Python代码的类方法

        Args:
            cls: 类方法引用
            code (str): 要执行的Python代码字符串
            language (str): 代码语言，目前仅支持Python
            *args: 代码执行时的位置参数
            **kwargs: 代码执行时的关键字参数

        Returns:
            Any: 代码执行的结果

        Raises:
            FailException: 当代码执行出现语法错误或值错误时抛出

        """
        try:
            # 使用SafeCodeExecutor安全执行代码
            # return SafeCodeExecutor.execute(code, *args, **kwargs)
            params = kwargs.get("params", {})
            if not params:
                error_msg = "main函数必须只有一个参数，且参数名为params"
                cls._raise_error(error_msg)

            if language == "python":
                url = "https://1253877543-1e74adsd9z.ap-guangzhou.tencentscf.com"
            else:
                url = "https://1253877543-etyxv3jldj.ap-guangzhou.tencentscf.com"
            headers = {"Content-Type": "application/json"}
            payload = json.dumps(
                {"code": code, "func_name": "main", "args": args, "kwargs": params},
                ensure_ascii=False,
            )
            response = requests.request(
                "POST",
                url,
                data=payload.encode("utf-8"),
                timeout=30,
                headers=headers,
            )
            return response.json().get("result", "")
        except (SyntaxError, ValueError) as e:
            # 捕获语法错误和值错误，构造错误信息并抛出异常
            error_msg = f"执行代码出错: {e}"
            cls._raise_error(error_msg)
