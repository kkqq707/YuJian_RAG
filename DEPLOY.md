# 部署与升级指南 (Phase 10)

## ⚠️ 数据安全警告

**严禁执行以下命令（会导致数据永久丢失）：**
- `docker compose down -v` — 删除所有 volume
- `docker volume rm yujian_storage yujian_data` — 删除数据卷
- `docker system prune --volumes` — 清理所有未使用 volume
- `docker volume prune` — 同上

## 资源分配 (2 vCPU / 4GB RAM / 4GB Swap)

| 服务 | CPU 上限 | 内存上限 | 内存预留 | PID 限制 |
|------|---------|---------|---------|---------|
| Backend | 1.8 | 3 GB | 1 GB | 128 |
| Frontend | 0.5 | 256 MB | 64 MB | 64 |
| 系统保留 | ~0.2 | ~744 MB | - | - |

容器日志限制:
- Backend: max 20MB × 5 = 100MB
- Frontend: max 20MB × 3 = 60MB

应用日志: RotatingFileHandler, max 10MB × 5 = 50MB

## 架构说明

### 数据存储

所有持久化数据使用 Docker **named volume**：

| Volume | 挂载路径 | 内容 |
|--------|---------|------|
| `yujian_storage` | `/app/storage` | SQLite 数据库、Chroma 向量库、日志、备份 |
| `yujian_data` | `/app/data` | 上传文件 |

模型文件使用 **bind mount**（只读）：
| 路径 | 挂载路径 |
|------|---------|
| `./models` | `/app/models:ro` |

### 健康检查

| 端点 | 用途 | 检查内容 |
|------|------|---------|
| `/api/v1/health/live` | Docker healthcheck | 进程存活 |
| `/api/v1/health/ready` | 负载均衡/监控 | 所有组件就绪 |
| `/api/v1/health` | 综合（向后兼容） | DB + Chroma |

## 日常操作

### 启动服务
```bash
docker compose up -d
```

### 停止服务
```bash
docker compose stop          # 安全：保留所有数据
# 或
docker compose down           # 安全：保留 volume（没加 -v）
```

### 查看日志
```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### 查看资源使用
```bash
docker stats --no-stream
```

### 查看服务状态
```bash
docker compose ps
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:8000/api/v1/health
```

### 查看磁盘使用
```bash
# 通过管理后台 API
curl -X GET http://localhost:8000/api/v1/admin/system \
  -H "Authorization: Bearer <admin_token>"
```

## 升级流程

### 使用部署脚本（推荐）
```bash
# 部署最新代码
bash scripts/deploy.sh

# 部署指定 commit
bash scripts/deploy.sh <commit-hash>
```

### 手动升级
```bash
# 1. 备份数据（必须！）
bash scripts/backup.sh

# 2. 拉取最新代码
git pull origin main

# 3. 构建并启动
docker compose build
docker compose up -d

# 4. 验证健康状态
bash scripts/smoke-test.sh
```

## 备份与恢复

### 手动备份
```bash
# 完整备份（含 SQLite .backup API、integrity check、SHA-256、manifest）
bash scripts/backup.sh

# 跳过 Chroma（快速备份）
bash scripts/backup.sh --skip-chroma
```

备份内容:
- SQLite 数据库（app.db + knowledge_metadata.db + WAL）
- Chroma 向量库
- 上传文件
- manifest.json（含 backup_id, timestamp, git_commit, alembic_revision, SHA-256）
- docker-compose.yml 副本

### 恢复演练（非破坏性）
```bash
# 在临时目录验证备份完整性
bash scripts/restore-test.sh backup_20260729_120000

# 启动临时实例验证
bash scripts/restore-test.sh backup_20260729_120000 --live
```

### 从备份恢复（破坏性）
```bash
# 1. 停止服务
docker compose stop

# 2. 解压备份
tar xzf backups/backup_20260729_120000.tar.gz -C backups/

# 3. 恢复数据库到 volume
docker run --rm \
  -v yujian_storage:/mnt/storage \
  -v $(pwd)/backups/backup_20260729_120000:/restore:ro \
  alpine sh -c 'cp /restore/storage/app.db /mnt/storage/app.db'

# 4. 启动服务
docker compose up -d
```

### 备份保留策略
- 每日备份保留 7 天
- 每周备份保留 4 份
- 发布前备份额外保留
- 磁盘不足时报警，不自动删除唯一备份

## 回滚

```bash
# 回滚代码和镜像（不恢复数据库）
bash scripts/rollback.sh <previous-commit>

# 回滚代码 + 恢复数据库（需确认）
bash scripts/rollback.sh <previous-commit> --restore-db
```

## 压测

```bash
# 场景 A: 健康与静态请求
python tests/load/run_load_tests.py --scenario A

# 场景 E: RAG 问答（并发 1）
python tests/load/run_load_tests.py --scenario E --rag-concurrency 1

# 全部场景（从低到高逐级）
python tests/load/run_load_tests.py --scenario all

# 指定目标地址
BASE_URL=http://your-server python tests/load/run_load_tests.py --scenario A
```

## 故障排查

### 容器不断重启
```bash
docker compose logs --tail=50 backend
# 检查 start_period 是否足够（模型加载需要 20-60s）
```

### OOMKilled
```bash
docker inspect yujian-backend | grep -i oom
# 检查内存限制是否过紧，调整 mem_limit
```

### SQLite busy
```bash
docker compose exec backend sh -c "cat /app/storage/logs/backend.log | grep -i 'busy\|lock'"
```

### Chroma 启动失败
```bash
curl http://localhost:8000/api/v1/system/rag-health \
  -H "Authorization: Bearer <admin_token>"
```

### 磁盘空间不足
```bash
# 检查管理后台磁盘信息
curl http://localhost:8000/api/v1/admin/system \
  -H "Authorization: Bearer <admin_token>" | jq .disk

# 清理 Docker 日志
docker compose logs --tail=100 backend > /dev/null  # 查看当前
# 日志轮转会自动限制，无需手动清理
```

### 数据库迁移失败
```bash
docker compose exec backend ls /app/storage/logs/
docker compose exec backend cat /app/storage/logs/migration_*.log
```

## 安全配置清单

- [x] 安全响应头（X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy）
- [x] Nginx 版本隐藏（server_tokens off）
- [x] .env / .git 路径禁止访问
- [x] 模型/数据目录禁止 HTTP 访问
- [x] 目录列表禁止
- [x] 上传大小限制（Nginx + 后端双重）
- [x] API 错误不暴露服务器路径
- [ ] HTTPS 配置（需域名 + 证书）
- [ ] HSTS 启用（需先配置 HTTPS）

## 禁止操作清单

- ❌ `docker compose down -v`
- ❌ `docker volume rm yujian_storage`
- ❌ `docker volume rm yujian_data`
- ❌ `docker system prune --volumes`
- ❌ `docker volume prune`
- ❌ 删除 `data/` 目录
- ❌ 在未备份的情况下重建 volume
- ❌ 修改 compose 从 named volume 改为 bind mount
- ❌ 将 `JWT_SECRET_KEY` 写入代码或 Git
- ❌ 在生产环境执行未经确认的压测
- ❌ 直接在生产数据库执行 destructive 操作
