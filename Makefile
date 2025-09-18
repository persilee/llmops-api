.PHONY: pipreqs migrate upgrade downgrade

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
