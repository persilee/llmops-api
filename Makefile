.PHONY: run celery test pipreqs migrate upgrade downgrade

# 启动项目
run:
	uv run flask --app app.http.app run --debug

# 启动 Celery 服务
celery:
	uv run celery -A app.http.app.celery worker --loglevel INFO --pool=threads --logfile storage/logs/celery.log

# 单元测试
test:
	uv run pytest tests

# 生成项目依赖文件
pipreqs:
	uv run pipreqs --ignore .venv --force

# 执行数据库迁移命令
# ARGS 可以传入迁移标识，用于指定特定的迁移版本
migrate:
	uv run flask --app app.http.app db migrate $(ARGS)

# 升级数据库到最新迁移版本
# ARGS 可以传入迁移标识，用于指定特定的迁移版本
upgrade:
	uv run flask --app app.http.app db upgrade $(ARGS)

# 降级数据库到指定迁移版本
# ARGS 可以传入迁移标识，用于指定特定的迁移版本
downgrade:
	uv run flask --app app.http.app db downgrade $(ARGS)
