#!/usr/bin/env bash
# ============================================================
# 企业智库 AI — 冒烟测试脚本
# 用于部署前快速验证核心功能
#
# 用法: bash scripts/smoke-test.sh
# 退出码: 0 = 全部通过, 非零 = 有失败项
# ============================================================

set -euo pipefail

BASE_URL="${SMOKE_TEST_BASE_URL:-http://localhost}"
PASS=0
FAIL=0
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; PASS=$((PASS + 1)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; FAIL=$((FAIL + 1)); }

# ---- 测试 1: 前端首页可达 ----
echo "=== 测试 1: 前端首页 ==="
if curl -sf -o /dev/null "$BASE_URL/"; then
  log_pass "前端首页返回 200"
else
  log_fail "前端首页不可达"
fi

# ---- 测试 2: 后端健康检查 ----
echo "=== 测试 2: 后端健康检查 ==="
HEALTH=$(curl -sf "$BASE_URL/api/v1/health" 2>&1) || true
if echo "$HEALTH" | grep -q '"backend":true'; then
  log_pass "后端健康检查通过: $HEALTH"
else
  log_fail "后端健康检查失败: $HEALTH"
fi

# ---- 测试 3: Chroma 向量库可用 ----
echo "=== 测试 3: Chroma 向量库 ==="
if echo "$HEALTH" | grep -q '"rag":true'; then
  log_pass "Chroma 向量库连接正常"
else
  log_fail "Chroma 向量库不可用"
fi

# ---- 测试 4: 登录接口可达 ----
echo "=== 测试 4: 登录接口 ==="
LOGIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' 2>&1) || true
if [ "$LOGIN_CODE" = "401" ] || [ "$LOGIN_CODE" = "200" ]; then
  log_pass "登录接口正常响应 (HTTP $LOGIN_CODE)"
else
  log_fail "登录接口异常 (HTTP $LOGIN_CODE)"
fi

# ---- 测试 5: 普通用户不能访问管理员接口 ----
echo "=== 测试 5: 权限隔离 ==="
ADMIN_RESP=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/admin/system" 2>&1) || true
if [ "$ADMIN_RESP" = "401" ] || [ "$ADMIN_RESP" = "403" ]; then
  log_pass "未认证用户访问 admin 接口返回 $ADMIN_RESP (正确拒绝)"
else
  log_fail "未认证用户访问 admin 接口返回 $ADMIN_RESP (应为 401/403)"
fi

# ---- 测试 6: 容器健康状态 ----
echo "=== 测试 6: 容器健康状态 ==="
if docker compose ps 2>/dev/null | grep -q "healthy"; then
  BACKEND_OK=$(docker compose ps 2>/dev/null | grep "backend" | grep -c "healthy" || true)
  FRONTEND_OK=$(docker compose ps 2>/dev/null | grep "frontend" | grep -c "healthy" || true)
  if [ "$BACKEND_OK" -ge 1 ] && [ "$FRONTEND_OK" -ge 1 ]; then
    log_pass "所有容器健康 (backend=$BACKEND_OK, frontend=$FRONTEND_OK)"
  else
    log_fail "部分容器不健康"
  fi
else
  log_fail "容器健康检查失败"
fi

# ---- 测试 7: 后端日志无未处理异常 ----
echo "=== 测试 7: 后端异常检查 ==="
ERROR_COUNT=$(docker compose logs --tail=100 backend 2>/dev/null | grep -ciE "Traceback|未处理异常|CRITICAL" 2>/dev/null | head -1 | tr -d '\r\n' || echo "0")
if [ "${ERROR_COUNT:-0}" -eq 0 ] 2>/dev/null; then
  log_pass "后端无未处理异常"
else
  log_fail "后端存在 $ERROR_COUNT 条异常日志"
fi

# ---- 测试 8: 环境变量检查 ----
echo "=== 测试 8: 环境变量 ==="
ENV_OK=true
for VAR in JWT_SECRET_KEY EMBEDDING_MODEL_NAME EMBEDDING_MODEL_PATH COLLECTION_NAME; do
  if docker compose exec -T backend sh -c "test -n \"\$$VAR\" && echo SET || echo MISSING" 2>/dev/null | grep -q "MISSING"; then
    log_fail "环境变量 $VAR 缺失"
    ENV_OK=false
  fi
done
if $ENV_OK; then
  log_pass "关键环境变量已设置"
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
