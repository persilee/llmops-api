from typing import Any

from src.core.workflow.entities.variable_entity import (
    VARIABLE_TYPE_DEFAULT_VALUE_MAP,
    VARIABLE_TYPE_MAP,
    VariableEntity,
    VariableValueType,
)
from src.core.workflow.entities.workflow_entity import WorkflowState


def extract_variables_from_state(
    variables: list[VariableEntity],
    state: WorkflowState,
) -> dict[str, Any]:
    """从工作流状态中提取变量值

    Args:
        variables: 变量实体列表，包含变量名、类型和值信息
        state: 工作流状态，包含节点执行结果等信息

    Returns:
        dict[str, Any]: 变量名到变量值的映射字典

    """
    # 1.初始化变量字典，用于存储最终提取的变量值
    variables_dict = {}

    # 2.遍历所有输入的变量实体
    for variable in variables:
        # 3.根据变量类型获取对应的类型转换类
        variable_type_cls = VARIABLE_TYPE_MAP.get(variable.type)

        # 4.判断变量值的类型：是直接输入的字面量还是引用其他节点的输出
        if variable.value.type == VariableValueType.LITERAL:
            # 4.1 如果是字面量，直接进行类型转换并存入字典
            variables_dict[variable.name] = variable_type_cls(variable.value.content)
        else:
            # 4.2 如果是引用，需要从节点执行结果中查找对应的值
            for node_result in state["node_results"]:
                # 4.2.1 检查当前节点是否是引用的目标节点
                if node_result.node_data.id == variable.value.content.ref_node_id:
                    # 4.2.2 从节点输出中获取引用的变量值，如果不存在则使用默认值
                    # 4.2.3 对获取的值进行类型转换并存入字典
                    variables_dict[variable.name] = variable_type_cls(
                        node_result.outputs.get(
                            variable.value.content.ref_var_name,
                            VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type),
                        ),
                    )
                    # 4.2.4 找到目标节点后即可跳出循环
                    break
    return variables_dict
