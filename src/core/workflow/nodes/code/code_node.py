import ast
from typing import Any, ClassVar

from langchain_core.runnables import RunnableConfig

from src.core.workflow.entities.node_entity import BaseNodeData, NodeResult, NodeStatus
from src.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from src.core.workflow.entities.workflow_entity import WorkflowState
from src.core.workflow.nodes.code.code_entity import CodeNodeData
from src.core.workflow.utils.helper import extract_variables_from_state
from src.exception.exception import FailException


class SafeCodeExecutor:
    """安全的代码执行器"""

    @classmethod
    def _validate_code(cls, tree: ast.AST) -> None:
        """验证代码的安全性"""
        forbidden_nodes = (
            ast.Import,
            ast.ImportFrom,
            ast.Exec,
            ast.Eval,
            ast.Attribute,  # 禁止属性访问
            ast.Subscript,  # 禁止下标访问
        )

        forbidden_names = {
            "eval",
            "exec",
            "compile",
            "__import__",
            "open",
            "file",
            "input",
            "raw_input",
            "globals",
            "locals",
            "vars",
            "dir",
            "reload",
            "help",
            "exit",
            "quit",
        }

        for node in ast.walk(tree):
            # 检查禁用的节点类型
            if isinstance(node, forbidden_nodes):
                if isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Name)
                        and node.func.id in forbidden_names
                    ):
                        error_msg = f"不允许使用 {node.func.id} 函数"
                        cls._raise_error(error_msg)
                else:
                    error_msg = "不允许使用此类型的操作"
                    cls._raise_error(error_msg)

            # 检查函数调用
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id not in cls.ALLOWED_BUILTINS
            ):
                error_msg = f"不允许使用 {node.func.id} 函数"
                cls._raise_error(error_msg)

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
        """安全执行代码"""
        try:
            # 解析代码
            tree = ast.parse(code)

            main_func = None
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    if node.name == "main":
                        if main_func:
                            error_msg = "代码只能包含一个名为main的函数"
                            cls._raise_error(error_msg)
                        if (
                            len(node.args.args) != 1
                            or node.args.args[0].arg != "params"
                        ):
                            error_msg = "main函数必须只有一个参数，且参数名为params"
                            cls._raise_error(error_msg)
                        main_func = node
                    else:
                        error_msg = "代码必须包含一个名为main的函数"
                        cls._raise_error(error_msg)
                else:
                    error_msg = "代码必须包含一个函数"
                    cls._raise_error(error_msg)
            if not main_func:
                error_msg = "代码必须包含一个名为main的函数"
                cls._raise_error(error_msg)

            # 验证代码安全性
            cls._validate_code(tree)

            # 编译代码
            compiled_code = compile(tree, filename="<ast>", mode="exec")

            # 创建受限的执行环境
            safe_globals = {
                "__builtins__": cls.ALLOWED_BUILTINS,
            }
            local_vars = {}

            # 执行代码
            exec(compiled_code, safe_globals, local_vars)  # noqa: S102

            # 返回 main 函数的结果
            if "main" in local_vars and callable(local_vars["main"]):
                return local_vars["main"](*args, **kwargs)

            error_msg = "代码必须包含一个名为main的函数"
            cls._raise_error(error_msg)

        except (SyntaxError, ValueError):
            cls._raise_error(error_msg)


class CodeNode(BaseNodeData):
    node_data: CodeNodeData

    def invoke(
        self,
        state: WorkflowState,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> WorkflowState:
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # TODO: 执行python 代码，后续实现
        result = self._execute_function(self.node_data.code, params=inputs_dict)

        if not isinstance(result, dict):
            self._raise_error("CodeNode 返回值必须为字典")

        outputs_dict = {}
        outputs = self.node_data.outputs
        for output in outputs:
            outputs_dict[output.name] = result.get(
                output.name,
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output.type),
            )

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs_dict,
                ),
            ],
        }

    @classmethod
    def _raise_error(cls, error_msg: str) -> None:
        """抛出 FailException 异常的内部方法"""
        raise FailException(error_msg)

    @classmethod
    def _execute_function(cls, code: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return SafeCodeExecutor.execute(code, *args, **kwargs)
        except (SyntaxError, ValueError) as e:
            error_msg = f"执行代码出错: {e}"
            cls._raise_error(error_msg)
