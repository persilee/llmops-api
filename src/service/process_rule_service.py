import re
from collections.abc import Callable
from dataclasses import dataclass

from injector import inject
from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter

from src.model.dataset import ProcessRule


@inject
@dataclass
class ProcessRuleService:
    """处理规则服务类，用于根据配置规则处理文本。

    该类提供了两个主要功能：
    1. 根据处理规则创建文本分割器，支持自定义分割参数
    2. 根据处理规则清理文本，支持多种预处理规则

    主要特性：
    - 支持递归字符文本分割
    - 支持正则表达式分隔符
    - 支持文本预处理，包括移除多余空格和URL/邮箱
    - 使用依赖注入模式
    """

    @classmethod
    def get_text_splitter_by_process_rule(
        cls,
        process_rule: ProcessRule,
        length_function: Callable[[str], int] = len,
        **kwargs: dict,
    ) -> TextSplitter:
        """根据处理规则创建文本分割器

        Args:
            process_rule (ProcessRule): 处理规则对象，包含分割配置信息
            length_function (Callable[[str], int], optional): 用于计算文本长度的函数，
            默认为len
            **kwargs: 其他传递给RecursiveCharacterTextSplitter的参数

        Returns:
            TextSplitter: 配置好的文本分割器实例

        Note:
            分割器使用递归字符分割方式，支持正则表达式分隔符

        """
        return RecursiveCharacterTextSplitter(
            chunk_size=process_rule.rule["segment"]["chunk_size"],
            chunk_overlap=process_rule.rule["segment"]["chunk_overlap"],
            separators=process_rule.rule["segment"]["separators"],
            is_separator_regex=True,
            length_function=length_function,
            **kwargs,
        )

    @classmethod
    def clean_text_by_process_rule(
        cls,
        text: str,
        process_rule: ProcessRule,
    ) -> str:
        """根据处理规则清理文本

        Args:
            text (str): 需要清理的原始文本
            process_rule (ProcessRule): 处理规则对象，包含预处理规则配置

        Returns:
            str: 清理后的文本

        Note:
            支持的预处理规则包括：
            1. remove_extra_space: 移除多余的空格和换行符
               - 将3个或以上的连续换行符替换为2个换行符
               - 将多个连续的空白字符替换为单个空格
            2. remove_url_and_email: 移除URL和邮箱地址
               - 移除符合邮箱格式的文本
               - 移除http/https开头的URL

        """
        # 遍历所有预处理规则
        for pre_process_rule in process_rule.rule["pre_process_rules"]:
            # 处理移除多余空格的规则
            if (
                pre_process_rule["id"] == "remove_extra_space"
                and pre_process_rule["enabled"] is True
            ):
                # 将3个或以上的连续换行符替换为2个换行符
                pattern = r"\n{3,}"
                text = re.sub(pattern, "\n\n", text)
                # 将多个连续的空白字符（包括制表符、空格等）替换为单个空格
                pattern = (
                    r"[\t\f\r\x20\u00a0\u1680\u180e\u2000-\u200a\u202f\u205f\u3000]{2,}"
                )
                text = re.sub(pattern, " ", text)

            # 处理移除URL和邮箱的规则
            if (
                pre_process_rule["id"] == "remove_url_and_email"
                and pre_process_rule["enabled"] is True
            ):
                # 移除邮箱地址
                pattern = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
                text = re.sub(pattern, "", text)
                # 移除http/https开头的URL
                pattern = r"https?://[^\s]+"
                text = re.sub(pattern, "", text)

        return text
