# 部署与升级指南

## ⚠️ 数据安全警告

**严禁执行以下命令（会导致数据永久丢失）：**
- `docker compose down -v` — 删除所有 volume
- `docker volume rm yujian_storage yujian_data` — 删除数据卷
- `docker system prune --volumes` — 清理所有未使用 volume
- `docker volume prune` — 同上

## 架构说明

### 数据存储

所有持久化数据使用 Docker **named volume**，存储在 Docker Desktop VM 中：

| Volume | 挂载路径 | 内容 |
|--------|---------|------|
| `yujian_storage` | `/app/storage` | SQLite 数据库(app.db)、Chroma 向量库、知识库元数据、日志、备份 |
| `yujian_data` | `/app/data` | 上传文件(uploads/) |

模型文件使用 **bind mount**（只读）：
| 路径 | 挂载路径 |
|------|---------|
| `./models` | `/app/models:ro` |

### Volume 信息

```
docker volume ls | grep yujian
# yujian_storage  — 主数据卷（数据库 + Chroma + 日志）
# yujian_data     — 上传文件卷
```

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
```

### 查看服务状态
```bash
docker compose ps
curl http://localhost:8000/api/v1/health
```

## 升级流程

### 1. 备份数据（必须！）
```bash
bash scripts/backup.sh
# 备份文件生成在: backups/YYYY-MM-DD.tar.gz
```

### 2. 拉取最新代码
```bash
git pull origin main
```

### 3. 停止服务
```bash
docker compose stop
```

### 4. 构建新镜像
```bash
docker compose build
```

### 5. 启动新容器
```bash
docker compose up -d
```

### 6. 验证健康状态
```bash
# 等待容器启动完成
docker compose ps
# 检查 health
curl http://localhost:8000/api/v1/health
# 应该返回: {"status":"healthy","backend":true,"database":true,"rag":true}
```

### 7. 验证数据完整性
```bash
# 登录旧账号，验证数据
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"test","password":"test123456"}'
# 应该成功返回 token
```

### 8. 如果出现问题，回滚
```bash
docker compose stop
# 从备份恢复数据
# 切回旧代码
git checkout <previous-commit>
docker compose build
docker compose up -d
```

## 备份与恢复

### 自动备份
应用内部已启用自动备份服务（24小时间隔），备份存储在 volume 内。

### 手动备份
```bash
bash scripts/backup.sh
```

### 从备份恢复
```bash
# 1. 停止服务
docker compose stop

# 2. 解压备份
BACKUP_DATE="2026-07-27"
tar xzf backups/${BACKUP_DATE}.tar.gz -C backups/restore/

# 3. 恢复数据库到 volume
docker run --rm \
  -v yujian_storage:/mnt/storage \
  -v $(pwd)/backups/restore/${BACKUP_DATE}:/restore \
  alpine sh -c 'cp /restore/app.db /mnt/storage/app.db'

# 4. 启动服务
docker compose up -d
```

## 故障排查

### 数据丢失问题
如果发现所有数据消失：
1. 检查 `docker volume ls` 是否包含 `yujian_storage` 和 `yujian_data`
2. 检查 `docker-compose.yml` 是否使用 named volume（非 bind mount）
3. 检查是否误执行了 `docker compose down -v`

### 数据库迁移失败
```
# 查看迁移日志
docker compose exec backend ls /app/storage/logs/
docker compose exec backend cat /app/storage/logs/migration_*.log
```

### Chroma 向量库问题
```
# 检查 Chroma 状态
curl http://localhost:8000/api/v1/system/rag-health
```

## 禁止操作清单

- ❌ `docker compose down -v`
- ❌ `docker volume rm yujian_storage`
- ❌ `docker volume rm yujian_data`
- ❌ `docker system prune --volumes`
- ❌ `docker volume prune`
- ❌ 删除 `data/` 目录（如果有）
- ❌ 在未备份的情况下重建 volume
- ❌ 修改 compose 从 named volume 改为 bind mount
