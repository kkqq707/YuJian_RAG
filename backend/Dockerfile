# ============================================================
# 企业智库 AI — Backend Dockerfile
# FastAPI + RAG 引擎
# ============================================================

FROM python:3.12-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PROJECT_ROOT=/app \
    # 离线模式（企业部署）
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1

WORKDIR /app

# ---- 安装系统依赖 ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- 安装 Python 依赖（利用 Docker 层缓存） ----
# 先复制 requirements 文件
COPY requirements.txt /app/requirements.txt
COPY backend/requirements.txt /app/backend/requirements.txt

# 安装项目根 requirements（RAG 核心依赖）
RUN pip install --no-cache-dir -r /app/requirements.txt
# 安装后端 requirements（FastAPI 等）
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
# 补充依赖（加密服务需要，非业务代码修改）
RUN pip install --no-cache-dir cryptography

# ---- 复制项目源码（从 backend/ 镜像到 /app/，扁平化目录结构） ----
# 安全: .dockerignore 已排除 .env / .git / storage / data / backup / logs
# 不得使用 COPY --no-ignore 或单独 ADD 敏感文件
COPY backend/ /app/backend/
# RAG 引擎代码（src/ 在项目根目录，backend 通过 from src.xxx 引用）
COPY src/ /app/src/
# ---- 复制本地模型（Embedding + Reranker）到 /app/models/ ----
# 模型文件在 backend/models/ 目录下，打包进镜像实现企业离线部署
# bind mount ./models:/app/models:ro 可作为可选热更新覆盖
COPY backend/models/ /app/models/

# ---- 创建运行时目录 ----
RUN mkdir -p /app/storage/logs /app/storage/backup /app/storage/chroma_db /app/data/uploads

# ---- 复制启动脚本 ----
COPY backend/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# ---- 暴露端口 ----
EXPOSE 8000

# ---- 健康检查 ----
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# ---- 启动命令（自动迁移 + 创建管理员 + 启动服务） ----
ENTRYPOINT ["/app/docker-entrypoint.sh"]
