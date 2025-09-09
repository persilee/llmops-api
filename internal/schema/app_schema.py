from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, Length


class CompletionReq(FlaskForm):
    query = StringField("query", validators=[
        DataRequired(message="请输入消息内容"),
        Length(max=1000, message="消息内容不能超过1000个字符")
    ])
