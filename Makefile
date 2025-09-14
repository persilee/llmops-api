.PHONY: pipreqs migrate upgrade downgrade

# 支持额外参数的版本
pipreqs:
	uv run pipreqs --ignore .venv --force

migrate:
	uv run flask --app app.http.app db migrate $(ARGS)

upgrade:
	uv run flask --app app.http.app db upgrade $(ARGS)

downgrade:
	uv run flask --app app.http.app db downgrade $(ARGS)
