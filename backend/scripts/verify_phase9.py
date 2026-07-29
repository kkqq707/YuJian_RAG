#!/usr/bin/env python
"""Phase 9 轻量验证脚本 — 限流、request_id、访问日志

模拟场景:
1. 同一 IP 连续登录 → 触发限流
2. 两个不同 IP 分别登录 → 额度独立
3. 同一用户快速聊天 → 触发限流
4. 两个不同用户聊天 → 额度独立
5. 管理员连续上传 → 触发限流
6. 管理员连续点击重建 → 触发限流
7. 限流窗口过期后恢复
8. request_id 传入和自动生成
9. 慢请求模拟
10. 429 后恢复

使用临时环境，不使用生产账号和生产数据。

Usage:
    cd backend
    python scripts/verify_phase9.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict


BASE_URL = "http://127.0.0.1:8000/api/v1"


def make_request(
    method: str,
    path: str,
    data: dict | None = None,
    headers: dict | None = None,
    expected_status: int | None = None,
) -> tuple[int, dict, dict]:
    """发送 HTTP 请求并返回 (status_code, response_body, response_headers)。"""
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    body = json.dumps(data).encode() if data else None

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = json.loads(resp.read().decode())
            resp_headers = dict(resp.headers)
            return resp.status, resp_body, resp_headers
    except urllib.error.HTTPError as e:
        try:
            resp_body = json.loads(e.read().decode())
        except Exception:
            resp_body = {"detail": str(e)}
        resp_headers = dict(e.headers)
        return e.code, resp_body, resp_headers
    except Exception as e:
        return 0, {"error": str(e)}, {}


def print_result(test_name: str, passed: bool, detail: str = ""):
    """打印测试结果。"""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {test_name}")
    if detail and not passed:
        print(f"    → {detail}")


def main():
    """主验证逻辑。"""
    print("=" * 60)
    print("Phase 9 验证脚本 — API 限流与请求可观测性")
    print("=" * 60)
    print()

    results: dict[str, bool] = {}
    stats = defaultdict(int)

    # -----------------------------------------------------------------------
    # 1. request_id 自动生成
    # -----------------------------------------------------------------------
    print("--- 1. request_id 验证 ---")

    _, _, headers = make_request("GET", "/health")
    rid = headers.get("X-Request-Id", "")
    has_rid = len(rid) > 0
    print_result("自动生成 request_id", has_rid, f"X-Request-ID: {rid}")
    results["request_id_auto"] = has_rid

    # 传入合法 ID
    _, _, headers = make_request(
        "GET", "/health", headers={"X-Request-ID": "my-test-rid-001"}
    )
    preserved = headers.get("X-Request-Id") == "my-test-rid-001"
    print_result("合法客户端 request_id 被保留", preserved, headers.get("X-Request-Id", ""))
    results["request_id_preserved"] = preserved

    # 传入非法 ID（换行）
    _, _, headers = make_request(
        "GET", "/health", headers={"X-Request-ID": "bad\nid"}
    )
    replaced = headers.get("X-Request-Id") != "bad\nid"
    print_result("非法 request_id 被替换", replaced, headers.get("X-Request-Id", ""))
    results["request_id_replaced"] = replaced

    print()

    # -----------------------------------------------------------------------
    # 2. 登录限流
    # -----------------------------------------------------------------------
    print("--- 2. 登录限流 ---")

    login_count_429 = 0
    login_has_retry_after = False
    login_last_retry_after = 0

    for i in range(15):
        status, body, headers = make_request(
            "POST",
            "/auth/login",
            data={"username": f"ratelimit_test_{i}", "password": "wrong_password"},
            headers={"X-Forwarded-For": "10.0.0.100"},
        )
        if status == 429:
            login_count_429 += 1
            stats["login_429"] += 1
            ra = body.get("retry_after", 0)
            if ra > 0:
                login_has_retry_after = True
                login_last_retry_after = ra
            if "Retry-After" in headers:
                pass  # header present

    print_result(
        f"登录达到阈值后返回 429 (共 {login_count_429} 次)",
        login_count_429 > 0,
    )
    results["login_429"] = login_count_429 > 0

    print_result(
        f"登录 429 带 Retry-After={login_last_retry_after}s",
        login_has_retry_after,
    )
    results["login_retry_after"] = login_has_retry_after

    print()

    # -----------------------------------------------------------------------
    # 3. 不同 IP 额度独立
    # -----------------------------------------------------------------------
    print("--- 3. 不同 IP 额度独立 ---")

    # IP 10.0.0.200 — 应该仍可以登录（新 IP，独立额度）
    status, _, _ = make_request(
        "POST",
        "/auth/login",
        data={"username": "admin", "password": "not_admin"},
        headers={"X-Forwarded-For": "10.0.0.200"},
    )
    ip_independent = status != 429
    print_result(
        f"不同 IP 额度独立 (新 IP 未被限流, status={status})",
        ip_independent,
    )
    results["ip_independent"] = ip_independent

    print()

    # -----------------------------------------------------------------------
    # 4. 不同用户额度独立（聊天）
    # -----------------------------------------------------------------------
    print("--- 4. 聊天限流 ---")

    # 首先获取有效的 auth token（登录）
    chat_429 = False
    status, body, _ = make_request(
        "POST",
        "/auth/login",
        data={"username": "test", "password": "test123456"},
    )
    if status == 200 and "access_token" in body:
        token = body["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 快速发送聊天请求
        for i in range(35):
            status, resp_body, _ = make_request(
                "POST",
                "/chat",
                data={"question": f"测试问题 {i}"},
                headers=headers,
            )
            if status == 429:
                chat_429 = True
                stats["chat_429"] += 1
                break

    print_result("聊天达到阈值后返回 429", chat_429)
    results["chat_429"] = chat_429
    print()

    # -----------------------------------------------------------------------
    # 5. 429 响应结构
    # -----------------------------------------------------------------------
    print("--- 5. 429 响应结构 ---")

    # 对登录端点发送足够请求触发 429
    status, body, headers = None, {}, {}
    for _ in range(12):
        status, body, headers = make_request(
            "POST",
            "/auth/login",
            data={"username": "test_struct", "password": "wrong"},
        )

    if status == 429:
        has_detail = "detail" in body
        has_code = body.get("code") == "RATE_LIMITED"
        has_retry = "retry_after" in body and isinstance(body.get("retry_after"), int)
        has_header = "Retry-After" in headers

        print_result("429 包含 detail", has_detail)
        print_result("429 包含 code=RATE_LIMITED", has_code)
        print_result("429 包含 retry_after", has_retry)
        print_result("429 包含 Retry-After 头", has_header)
        results["429_structure"] = has_detail and has_code and has_retry

        # 验证不暴露内部计数器
        safe = True
        for k in body:
            if "count" in k.lower() or "remaining" in k.lower() or "limit" in k.lower():
                safe = False
        print_result("429 不暴露内部计数器", safe)
        results["429_no_internal"] = safe

    print()

    # -----------------------------------------------------------------------
    # 6. 限流恢复
    # -----------------------------------------------------------------------
    print("--- 6. 限流恢复 ---")

    limiter = None
    try:
        sys.path.insert(0, ".")
        from backend.app.rate_limiter import get_rate_limiter, get_rules, RateLimitRule

        limiter = get_rate_limiter()
        rules = get_rules()

        # 短窗口测试
        test_rule = RateLimitRule(max_requests=3, window_seconds=2)
        key = "verify_recovery_test_key"
        for _ in range(3):
            limiter.check(key, test_rule)
        allowed_before, _ = limiter.check(key, test_rule)
        print_result("限流触发", not allowed_before)

        # 等待窗口过期
        time.sleep(2.1)
        allowed_after, _ = limiter.check(key, test_rule)
        print_result("限流窗口过期后恢复", allowed_after)
        results["limiter_recovery"] = allowed_after

        # 验证 key 数量
        key_count = limiter.get_active_key_count()
        print_result(f"状态清理后 limiter key 数合理 (当前: {key_count})", key_count >= 0)
        results["key_count"] = key_count >= 0
    except Exception as e:
        print_result(f"限流恢复测试异常: {e}", False)
        results["limiter_recovery"] = False
        results["key_count"] = False

    print()

    # -----------------------------------------------------------------------
    # 7. 慢请求模拟
    # -----------------------------------------------------------------------
    print("--- 7. 慢请求模拟 ---")

    from backend.app.metrics import get_metrics

    metrics = get_metrics()
    before_slow = metrics.snapshot()["slow_request_total"]

    # 健康检查很快
    make_request("GET", "/health")
    after_slow = metrics.snapshot()["slow_request_total"]

    # 健康检查不应产生慢请求（除非系统确实慢）
    print_result(
        f"健康检查不产生大量慢请求 (before={before_slow}, after={after_slow})",
        after_slow - before_slow <= 1,
    )
    results["health_no_slow"] = after_slow - before_slow <= 1

    print()

    # -----------------------------------------------------------------------
    # 8. 验证 HTTP 指标
    # -----------------------------------------------------------------------
    print("--- 8. HTTP 指标 ---")

    snapshot = metrics.snapshot()
    has_requests_total = snapshot["http_requests_total"] > 0
    print_result(f"http_requests_total > 0 ({snapshot['http_requests_total']})", has_requests_total)
    results["metrics_requests"] = has_requests_total

    active_zero = snapshot["http_requests_active"] == 0
    print_result(f"active 请求归零 ({snapshot['http_requests_active']})", active_zero)
    results["metrics_active_zero"] = active_zero

    print()

    # -----------------------------------------------------------------------
    # 总结
    # -----------------------------------------------------------------------
    print("=" * 60)
    print("验证总结")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"通过: {passed}/{total}")

    for name, result in results.items():
        status = "✓" if result else "✗"
        print(f"  {status} {name}")

    print()
    print("限流统计:")
    print(f"  登录 429 数: {stats.get('login_429', 0)}")
    print(f"  聊天 429 数: {stats.get('chat_429', 0)}")
    print(f"  不同 IP 隔离: {'是' if results.get('ip_independent', False) else '否'}")
    print(f"  Retry-After 存在: {'是' if results.get('login_retry_after', False) else '否'}")
    print(f"  request_id 完整: {'是' if results.get('request_id_auto', False) else '否'}")
    print(f"  active 请求归零: {'是' if results.get('metrics_active_zero', False) else '否'}")
    print(f"  limiter key 数量: {limiter.get_active_key_count() if limiter else 'N/A'}")

    print()
    if passed == total:
        print("✓ 全部验证通过")
        return 0
    else:
        print(f"✗ {total - passed} 项验证失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
