from wtforms import Field


class ListField(Field):
    """自定义表单字段类，用于处理列表类型的数据

    继承自wtforms.Field，用于处理表单中的列表类型数据输入。
    可以处理多个值的输入，并将其转换为Python列表。
    """

    data: list = None  # 存储字段的数据，类型为列表

    def process_formdata(self, valuelist: list[any]) -> None:
        """处理表单提交的数据

        Args:
            valuelist (list[any]): 从表单接收到的值列表

        将表单提交的数据转换为列表格式存储。
        如果输入是有效的列表，则直接存储；
        否则初始化为空列表。

        """
        if valuelist is not None and isinstance(valuelist, list):
            self.data = valuelist
        else:
            self.data = []

    def _value(self) -> list:
        """返回字段的值

        Returns:
            list: 返回存储的数据，如果数据为空则返回空列表

        用于表单渲染时获取字段的值。
        确保总是返回一个列表，即使数据为空。

        """
        return self.data if self.data else []


class DictField(Field):
    """自定义表单字段类，用于处理字典类型的数据

    继承自wtforms.Field，用于处理表单中的字典类型数据输入。
    可以处理键值对形式的输入，并将其转换为Python字典。
    """

    data: dict = None  # 存储字段的数据，类型为字典

    def process_formdata(self, valuelist: list[any]) -> None:
        """处理表单提交的数据

        Args:
            valuelist (list[any]): 从表单接收到的值列表

        将表单提交的数据转换为字典格式存储。
        如果输入是有效的字典，则直接存储；
        否则保持为None。

        """
        if (
            valuelist is not None
            and len(valuelist) > 0
            and isinstance(valuelist[0], dict)
        ):
            self.data = valuelist[0]

    def _value(self) -> dict:
        """返回字段的值

        Returns:
            dict: 返回存储的数据，如果数据为空则返回None

        用于表单渲染时获取字段的值。
        返回存储的字典数据。

        """
        return self.data
