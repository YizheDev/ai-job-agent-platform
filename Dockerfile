# ============================================================
# AI求职智能管家 - Docker 镜像
# 基于 Playwright 官方镜像，内置 Chromium 及所有系统依赖
# ============================================================

FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

LABEL maintainer="AI Job Agent Team"
LABEL description="AI求职智能管家 - 生产部署镜像"

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOCKER_CONTAINER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# 先复制依赖清单，利用 Docker 层缓存
# 锁定 playwright 版本与基础镜像一致，避免浏览器/驱动版本不匹配
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir playwright==1.48.0 \
    && playwright install --with-deps chromium

# 复制项目源码
COPY . .

# 创建数据持久化目录并设置权限（在切换用户前完成）
RUN mkdir -p /app/data/resumes /app/data/backups /app/data/screenshots /app/logs \
    && chown -R pwuser:pwuser /app \
    && chmod +x /app/deploy/entrypoint.sh

# 非 root 用户运行（pwuser 是官方镜像内置用户）
USER pwuser

EXPOSE 7860

# start-period=60s: Gradio + LangGraph 冷启动可能需要 30-50s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
