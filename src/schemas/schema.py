from wtforms import Field


class ListField(Field):
    data: list = None

    def process_formdata(self, valuelist: list[any]) -> None:
        if valuelist is not None and isinstance(valuelist, list):
            self.data = valuelist
        else:
            self.data = []

    def _value(self) -> list:
        return self.data if self.data else []
