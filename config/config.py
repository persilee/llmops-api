class Config:
    def __init__(self):
        # 将CSRF（跨站请求伪造）保护设置为禁用状态
        self.WTF_CSRF_ENABLED = False
