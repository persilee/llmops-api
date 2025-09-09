import os

from flask import request
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam

from internal.schema.app_schema import CompletionReq


class AppHandler:
    """
    AppHandler 是一个处理聊天机器人相关请求的处理器类。

    核心功能：
    - 提供聊天机器人接口，处理用户查询并返回 AI 助手的回复

    代码示例：
        ```python
        response = AppHandler.completion()
        print(response)  # 打印 AI 助手的回复
        ```

    使用限制：
    - 需要正确配置环境变量 OPENAI_API_BASE_URL
    - 请求必须包含有效的 query 参数
    """

    @staticmethod
    def completion():
        """聊天机器人接口"""

        req = CompletionReq()

        if not req.validate():
            return req.errors

        query = request.json.get("query")
        client = OpenAI(base_url=os.getenv("OPENAI_API_BASE_URL"))
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                ChatCompletionUserMessageParam(role="user", content=query)
            ]
        )

        return completion.choices[0].message.content
