class Redprint:
    def __init__(self, name):
        self.name = name
        self.mound = []

    def route(self, rule, **options):
        def decorator(func):
            self.mound.append((func, rule, options))
            return func

        return decorator

    def register(self, bp, url_prefix=None):
        for func, rule, options in self.mound:
            endpoint = options.pop("endpoint", func.__name__)
            bp.add_url_rule(url_prefix + rule, endpoint, func, **options)
