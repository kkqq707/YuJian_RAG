#!/usr/bin/env bash
# ============================================================
# 企业智库 AI — 冒烟测试脚本 (Phase 10 增强)
# 用于部署前/后快速验证核心功能
#
# 用法: bash scripts/smoke-test.sh [--admin]
# 退出码: 0 = 全部通过, 非零 = 有失败项
# ============================================================

set -euo pipefail

BASE_URL="${SMOKE_TEST_BASE_URL:-http://localhost}"
ADMIN_MODE=false
if [ "${1:-}" = "--admin" ]; then
    ADMIN_MODE=true
fi

PASS=0
FAIL=0
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; PASS=$((PASS + 1)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; FAIL=$((FAIL + 1)); }
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

# ---- 测试 1: 前端首页可达 ----
echo "=== 测试 1: 前端首页 ==="
if curl -sf -o /dev/null "$BASE_URL/"; then
  log_pass "前端首页返回 200"
else
  log_fail "前端首页不可达"
fi

# ---- 测试 2: 后端 Liveness ----
echo "=== 测试 2: 后端 Liveness ==="
LIVE=$(curl -sf "$BASE_URL/api/v1/health/live" 2>&1) || true
if echo "$LIVE" | grep -q '"alive"'; then
  log_pass "Liveness 正常: $LIVE"
else
  log_fail "Liveness 失败: $LIVE"
fi

# ---- 测试 3: 后端 Readiness ----
echo "=== 测试 3: 后端 Readiness ==="
READY_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/health/ready" 2>&1) || true
if [ "$READY_CODE" = "200" ] || [ "$READY_CODE" = "503" ]; then
  log_pass "Readiness 响应 (HTTP $READY_CODE)"
else
  log_fail "Readiness 异常 (HTTP $READY_CODE)"
fi

# ---- 测试 4: 后端综合健康检查 ----
echo "=== 测试 4: 后端健康检查 ==="
HEALTH=$(curl -sf "$BASE_URL/api/v1/health" 2>&1) || true
if echo "$HEALTH" | grep -q '"backend":true'; then
  log_pass "后端健康检查通过"
else
  log_fail "后端健康检查失败: $HEALTH"
fi

# Chroma 检查
if echo "$HEALTH" | grep -q '"rag":true'; then
  log_info "  Chroma 连接正常"
else
  log_info "  Chroma 暂不可用（首次部署正常）"
fi

# ---- 测试 5: request_id 响应头 ----
echo "=== 测试 5: X-Request-ID ==="
REQ_ID=$(curl -sf -I "$BASE_URL/api/v1/health/live" 2>&1 | grep -i "x-request-id" || echo "")
if [ -n "$REQ_ID" ]; then
  log_pass "X-Request-ID 响应头存在"
else
  log_fail "X-Request-ID 响应头缺失"
fi

# ---- 测试 6: 安全响应头 ----
echo "=== 测试 6: 安全响应头 ==="
SECURITY_HEADERS=$(curl -sf -I "$BASE_URL/api/v1/health" 2>&1) || true
HEADER_FAILS=0
for header in "X-Content-Type-Options" "X-Frame-Options" "Referrer-Policy"; do
  if echo "$SECURITY_HEADERS" | grep -qi "$header"; then
    :
  else
    log_info "  $header 缺失"
    HEADER_FAILS=$((HEADER_FAILS + 1))
  fi
done
if [ "$HEADER_FAILS" -eq 0 ]; then
  log_pass "安全响应头完整"
else
  log_fail "$HEADER_FAILS 个安全响应头缺失"
fi

# ---- 测试 7: 登录接口 ----
echo "=== 测试 7: 登录接口 ==="
LOGIN_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"test_nonexistent","password":"test"}' 2>&1) || true
LOGIN_CODE=$(echo "$LOGIN_RESP" | tail -1)
if [ "$LOGIN_CODE" = "401" ] || [ "$LOGIN_CODE" = "200" ] || [ "$LOGIN_CODE" = "429" ]; then
  log_pass "登录接口正常 (HTTP $LOGIN_CODE)"
else
  log_fail "登录接口异常 (HTTP $LOGIN_CODE)"
fi

# ---- 测试 8: 权限隔离 ----
echo "=== 测试 8: 权限隔离 ==="
ADMIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/admin/system" 2>&1) || true
if [ "$ADMIN_CODE" = "401" ] || [ "$ADMIN_CODE" = "403" ]; then
  log_pass "未认证用户被拒绝访问 /admin/system (HTTP $ADMIN_CODE)"
else
  log_fail "未认证用户可访问 /admin/system (HTTP $ADMIN_CODE，应为 401/403)"
fi

# ---- 测试 9: Nginx 配置 ----
echo "=== 测试 9: Nginx 配置 ==="
# 检查 server_tokens off
SERVER_HEADER=$(curl -sf -I "$BASE_URL/" 2>&1 | grep -i "server:" || echo "")
if echo "$SERVER_HEADER" | grep -qi "nginx/[0-9]"; then
  log_fail "Nginx 版本暴露: $SERVER_HEADER"
else
  log_pass "Nginx 版本已隐藏"
fi

# 禁止目录列表
DIR_LIST=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/api/" 2>&1) || true
if [ "$DIR_LIST" != "200" ]; then
  log_info "  目录列表已禁止"
else
  log_info "  /api/ 返回 200（可能有默认文档）"
fi

# ---- 测试 10: 上传大小限制 ----
echo "=== 测试 10: 上传大小限制 ==="
UPLOAD_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/documents/upload/" \
  -H "Content-Type: multipart/form-data" 2>&1) || true
# 预期 401（未认证）或 422（参数错误），不是 413
if [ "$UPLOAD_CODE" != "413" ]; then
  log_info "上传接口可达 (HTTP $UPLOAD_CODE)"
else
  log_fail "上传接口返回 413"
fi

# ---- 测试 11: Vue Router fallback ----
echo "=== 测试 11: Vue Router ==="
SPA_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/chat" 2>&1) || true
SPA_CONTENT_TYPE=$(curl -sf -I "$BASE_URL/chat" 2>&1 | grep -i "content-type:" || echo "")
if [ "$SPA_CODE" = "200" ]; then
  if echo "$SPA_CONTENT_TYPE" | grep -qi "html"; then
    log_pass "Vue Router fallback 正常（/chat 返回 HTML）"
  else
    log_info "  /chat 返回非 HTML（可能是 API 响应）"
  fi
else
  log_fail "Vue Router fallback 失败 (/chat HTTP $SPA_CODE)"
fi

# ---- 测试 12: .env 路径禁用 ----
echo "=== 测试 12: 敏感路径保护 ==="
ENV_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/.env" 2>&1) || true
if [ "$ENV_CODE" = "403" ] || [ "$ENV_CODE" = "404" ]; then
  log_pass ".env 路径已保护 (HTTP $ENV_CODE)"
else
  log_fail ".env 路径可访问 (HTTP $ENV_CODE)"
fi

# ---- 测试 13: 容器健康状态 ----
echo "=== 测试 13: 容器健康状态 ==="
if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
  if docker compose ps 2>/dev/null | grep -q "healthy\|Up"; then
    log_pass "容器运行中"
    docker compose ps 2>/dev/null | grep -E "backend|frontend" || true
  else
    log_info "容器状态无法检测（非 Docker 环境）"
  fi
else
  log_info "Docker 不可用，跳过容器状态检查"
fi

# ---- Admin 模式附加测试 ----
if [ "$ADMIN_MODE" = true ]; then
  echo ""
  echo "=== Admin 模式附加测试 ==="

  # 测试管理员登录
  echo "=== 测试 A1: 管理员登录 ==="
  ADMIN_LOGIN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin123456"}' 2>&1) || true
  ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

  if [ -n "$ADMIN_TOKEN" ]; then
    log_pass "管理员登录成功"

    # 测试管理接口
    echo "=== 测试 A2: 管理接口 ==="
    ADMIN_SYS=$(curl -sf "$BASE_URL/api/v1/admin/system" \
      -H "Authorization: Bearer $ADMIN_TOKEN" 2>&1) || true
    if [ -n "$ADMIN_SYS" ]; then
      log_pass "管理接口可达"
    else
      log_fail "管理接口不可达"
    fi

    # 测试 RAG 健康
    echo "=== 测试 A3: RAG 健康 ==="
    RAG_HEALTH=$(curl -sf "$BASE_URL/api/v1/system/rag-health" \
      -H "Authorization: Bearer $ADMIN_TOKEN" 2>&1) || true
    if [ -n "$RAG_HEALTH" ]; then
      log_pass "RAG 健康接口可达"
    else
      log_info "RAG 健康接口暂不可用"
    fi

    # 测试模型健康
    echo "=== 测试 A4: 模型健康 ==="
    MODEL_HEALTH=$(curl -sf "$BASE_URL/api/system/model-health" \
      -H "Authorization: Bearer $ADMIN_TOKEN" 2>&1) || true
    if echo "$MODEL_HEALTH" | grep -q "embedding"; then
      log_pass "模型健康接口正常"
    else
      log_info "模型健康接口暂不可用"
    fi
  else
    log_fail "管理员登录失败"
  fi
fi

# ---- 结果汇总 ----
echo ""
echo "========================================"
echo "  冒烟测试结果: $PASS 通过, $FAIL 失败"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}存在失败项，部署阻断！${NC}"
  exit 1
else
  echo -e "${GREEN}全部通过，可以部署。${NC}"
  exit 0
fi
