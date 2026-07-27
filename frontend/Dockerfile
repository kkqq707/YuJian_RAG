# ============================================================
# 企业智库 AI — Frontend Dockerfile
# Vue 3 + Vite → Nginx 生产部署
# ============================================================

# ---- Stage 1: 构建 ----
FROM node:20-alpine AS builder

WORKDIR /app

# 安装依赖（利用 Docker 层缓存）
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps

# 复制前端源码（.dockerignore 排除 .env / .env.* 等敏感文件）
COPY frontend/ ./

# 构建生产版本
RUN npm run build

# ---- Stage 2: Nginx 服务 ----
FROM nginx:1.27-alpine

# 安装 curl（用于健康检查）
RUN apk add --no-cache curl

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制自定义 Nginx 配置
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 健康检查（检查 nginx 自身，不依赖后端）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
