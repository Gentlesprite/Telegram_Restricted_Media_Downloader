FROM python:3.13.2-slim

# 设置工作目录。
WORKDIR /app

# 设置环境变量。
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_CONFIG_HOME=/app \
    TERM=xterm-256color

# 安装系统依赖+Python依赖，编译后清理，全部合并为一个RUN层以减小镜像体积。
COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
        libmediainfo0v5 \
        gcc \
        g++ \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc g++ \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件。
COPY main.py .
COPY module/ ./module/

# 创建配置目录、下载目录、会话目录和临时目录。
RUN mkdir -p /app/TRMD /app/downloads /app/sessions /app/temp

# 设置挂载点。
VOLUME ["/app/TRMD", "/app/downloads", "/app/sessions", "/app/temp"]

# 运行应用。
# --config: 用户配置存到挂载目录，容器重启不丢失。
# session_directory和temp_directory可在config.yaml中自行配置。
CMD ["python", "main.py", "--config", "/app/TRMD/config.yaml"]
