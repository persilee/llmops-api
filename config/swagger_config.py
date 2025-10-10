swagger_template = {
    "openapi": "3.0.4",
    "info": {
        "title": "LLMops API",
        "description": "LLMops 项目 API 文档",
        "version": "0.0.1",
        "contact": {
            "name": "API 支持",
            "email": "",
            "url": "",
            "responsibleOrganization": "",
            "responsibleDeveloper": "",
        },
        "termsOfService": "",
    },
    "servers": [
        {
            "url": "http://127.0.0.1:5000",
            "description": "本地开发环境",
        },
    ],
    "schemes": ["http", "https"],
    "components": {},
}


swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,  # noqa: ARG005
            "model_filter": lambda tag: True,  # noqa: ARG005
        },
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}
