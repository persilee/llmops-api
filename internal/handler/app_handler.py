from flask import request
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam


class AppHandler:
    """应用控制器"""

    @staticmethod
    def completion():
        """聊天机器人接口"""
        query = request.json.get("query")
        client = OpenAI(
            api_key="sk-16FJrevQm3gJ4xkWOVV4pSsJoXHZwSx6c42BT9DM6XwXsCZR",
            base_url='https://api.agicto.cn/v1'
        )
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                ChatCompletionUserMessageParam(role="user", content=query)
            ]
        )

        return completion.choices[0].message.content

    @staticmethod
    def ping():
        return "pong"
