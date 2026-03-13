# 使用python:3.11版本作为基础镜像
FROM python:3.11 AS base

# ==========================
# 阿里云 Debian 源
# ==========================
RUN echo "deb https://mirrors.aliyun.com/debian bookworm main non-free contrib" > /etc/apt/sources.list \
    && echo "deb https://mirrors.aliyun.com/debian-security bookworm-security main non-free contrib" >> /etc/apt/sources.list \
    && echo "deb https://mirrors.aliyun.com/debian bookworm-updates main non-free contrib" >> /etc/apt/sources.list
# 安装编译器（python:3.11 是 Debian，用 apt-get）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    python3-dev \
    libffi-dev \
    musl-dev \
    make \
    && rm -rf /var/lib/apt/lists/*

# 将requirements.txt拷贝到根目录下
COPY requirements.txt .

# 构建缓存并使用pip安装严格版本的requirements.txt
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com && \
    pip config set global.timeout 300 && \
    # 关键：优先装预编译的 wheel 包，避免源码编译
    pip install --no-cache-dir --upgrade pip && \
    pip install --prefix=/pkg --no-cache-dir -r requirements.txt

# 二阶段生产环境构建
FROM base AS production

# 设置工作目录
WORKDIR /app/api

# 定义环境变量
ENV FLASK_APP=app/http/app.py
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV NLTK_DATA=/app/api/src/core/unstructured/nltk_data
ENV HF_ENDPOINT=https://hf-mirror.com

# 设置容器时区为中国标准时间，避免时区错误
ENV TZ Asia/Shanghai

# 拷贝第三方依赖包+源码文件
COPY --from=base /pkg /usr/local
COPY . /app/api

# 拷贝运行脚本并设置权限
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露5001端口
EXPOSE 5001

# 运行脚本并启动项目
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
