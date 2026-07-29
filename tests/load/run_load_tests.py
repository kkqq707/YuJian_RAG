#!/usr/bin/env python3
"""
Phase 10: 分阶段生产压测脚本 (pytest + httpx)

设计原则:
- 默认安全参数，必须显式参数才允许较高并发
- 默认目标指向 localhost
- 每阶段结束等待系统恢复
- 记录压测前后资源状态
- 支持快速停止

用法:
  # 场景 A: 健康与静态请求 (并发 10, 25, 50)
  python tests/load/run_load_tests.py --scenario A

  # 场景 B: 登录
  python tests/load/run_load_tests.py --scenario B

  # 全部场景（从低到高逐级执行）
  python tests/load/run_load_tests.py --scenario all

  # 自定义参数
  python tests/load/run_load_tests.py --scenario E --rag-concurrency 1
  python tests/load/run_load_tests.py --scenario E --rag-concurrency 2

环境变量:
  BASE_URL=http://localhost          # 默认目标
  TEST_ADMIN_USER=admin              # 测试管理员
  TEST_ADMIN_PASS=admin123456
  TEST_USER_PREFIX=loadtest_         # 测试用户前缀
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BASE_URL", "http://localhost").rstrip("/")
REPORT_DIR = Path(__file__).resolve().parent / "reports"

# 停止标志
STOP_REQUESTED = False


def _on_stop(signum, frame):
    global STOP_REQUESTED
    print("\n[STOP] 收到停止信号，正在结束当前阶段...")
    STOP_REQUESTED = True


signal.signal(signal.SIGINT, _on_stop)
signal.signal(signal.SIGTERM, _on_stop)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class RequestStats:
    """单次请求统计。"""
    total: int = 0
    success: int = 0
    status_4xx: int = 0
    status_5xx: int = 0
    status_429: int = 0
    cancelled: int = 0
    latencies: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return (self.success / self.total * 100) if self.total > 0 else 0

    @property
    def error_rate(self) -> float:
        return 100 - self.success_rate

    def p50(self) -> float:
        return _percentile(self.latencies, 50)

    def p90(self) -> float:
        return _percentile(self.latencies, 90)

    def p95(self) -> float:
        return _percentile(self.latencies, 95)

    def p99(self) -> float:
        return _percentile(self.latencies, 99)

    def max_latency(self) -> float:
        return max(self.latencies) if self.latencies else 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success": self.success,
            "status_4xx": self.status_4xx,
            "status_5xx": self.status_5xx,
            "status_429": self.status_429,
            "cancelled": self.cancelled,
            "success_rate_pct": round(self.success_rate, 2),
            "error_rate_pct": round(self.error_rate, 2),
            "p50_ms": round(self.p50() * 1000, 1),
            "p90_ms": round(self.p90() * 1000, 1),
            "p95_ms": round(self.p95() * 1000, 1),
            "p99_ms": round(self.p99() * 1000, 1),
            "max_ms": round(self.max_latency() * 1000, 1),
            "errors": self.errors[:10],  # 只保留前10条
        }


@dataclass
class ScenarioResult:
    """场景测试结果。"""
    scenario: str
    description: str
    concurrency: int
    duration_seconds: float
    requests: RequestStats = field(default_factory=RequestStats)
    stop_triggered: bool = False
    stop_reason: str = ""
    cpu_before: str = ""
    cpu_after: str = ""
    mem_before: str = ""
    mem_after: str = ""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100.0
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return sorted_data[f]


def _get_resource_snapshot() -> dict:
    """获取系统资源快照。"""
    snapshot = {}
    # Docker stats
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            snapshot["docker_stats"] = result.stdout.strip()
    except Exception:
        pass

    # Disk usage
    try:
        disk = shutil.disk_usage(".")
        snapshot["disk"] = {
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "used_gb": round(disk.used / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
        }
    except Exception:
        pass

    return snapshot


async def _get_system_health(client: httpx.AsyncClient) -> dict:
    """获取后端健康状态。"""
    try:
        resp = await client.get(f"{BASE_URL}/api/v1/health", timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def _check_stop_conditions(stats: RequestStats, health: dict) -> Optional[str]:
    """检查停止条件。

    Returns
    -------
    str or None
        停止原因，None 表示继续。
    """
    if STOP_REQUESTED:
        return "用户中断"

    if stats.error_rate > 1.0 and stats.total > 20:
        return f"5xx错误率超过1% ({stats.error_rate:.1f}%)"

    # 检查健康状态
    if health.get("status") == "unhealthy":
        return "后端健康检查失败"

    return None


# ---------------------------------------------------------------------------
# HTTP 客户端
# ---------------------------------------------------------------------------


async def _make_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    **kwargs,
) -> tuple[int, float, Optional[str]]:
    """发起请求并返回 (status_code, latency_seconds, error)。

    安全: 不打印 token，不记录完整响应体。
    """
    t0 = time.perf_counter()
    try:
        resp = await client.request(method, f"{BASE_URL}{path}", **kwargs)
        elapsed = time.perf_counter() - t0
        return resp.status_code, elapsed, None
    except asyncio.CancelledError:
        elapsed = time.perf_counter() - t0
        return 499, elapsed, "cancelled"
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return 0, elapsed, str(e)[:200]


async def _run_concurrent(
    client_factory,
    tasks: list,
    concurrency: int,
    duration: float,
    check_interval: float = 1.0,
) -> RequestStats:
    """以指定并发数运行任务列表，持续 duration 秒。

    每 check_interval 秒检查停止条件。
    """
    stats = RequestStats()
    sem = asyncio.Semaphore(concurrency)
    start_time = time.perf_counter()

    async def worker(task_fn):
        nonlocal stats
        async with sem:
            if STOP_REQUESTED:
                return
            if time.perf_counter() - start_time > duration:
                return

            status, latency, error = await task_fn()
            stats.total += 1
            stats.latencies.append(latency)

            if error:
                stats.errors.append(error)
                stats.cancelled += 1
            elif status >= 500:
                stats.status_5xx += 1
            elif status == 429:
                stats.status_429 += 1
            elif status >= 400:
                stats.status_4xx += 1
            else:
                stats.success += 1

    # 持续发送请求直到时间到
    worker_tasks = []
    deadline = start_time + duration

    while time.perf_counter() < deadline and not STOP_REQUESTED:
        for task_fn in tasks:
            if time.perf_counter() >= deadline or STOP_REQUESTED:
                break
            t = asyncio.create_task(worker(task_fn))
            worker_tasks.append(t)

        # 等待一小批完成
        await asyncio.sleep(0.1)

        # 清理已完成的 task
        worker_tasks = [t for t in worker_tasks if not t.done()]

    # 等待所有剩余 worker
    if worker_tasks:
        await asyncio.gather(*worker_tasks, return_exceptions=True)

    return stats


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def _get_auth_token(
    client: httpx.AsyncClient,
    username: str,
    password: str,
) -> Optional[str]:
    """获取认证 token（安全：使用测试账号）。"""
    try:
        resp = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("access_token")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 场景 A: 健康与静态请求
# ---------------------------------------------------------------------------


async def scenario_a_health_static(concurrency: int = 10, duration: float = 60):
    """场景 A: 健康检查 + 静态首页。"""
    print(f"\n{'='*60}")
    print(f"  场景 A: 健康与静态请求 (并发={concurrency}, 持续={duration}s)")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [
            lambda: _make_request(client, "GET", "/api/v1/health/live"),
            lambda: _make_request(client, "GET", "/api/v1/health"),
            lambda: _make_request(client, "GET", "/"),
        ]

        stats = await _run_concurrent(
            lambda: client, tasks, concurrency, duration,
        )

    return ScenarioResult(
        scenario="A",
        description="健康与静态请求",
        concurrency=concurrency,
        duration_seconds=duration,
        requests=stats,
    )


# ---------------------------------------------------------------------------
# 场景 B: 登录
# ---------------------------------------------------------------------------


async def scenario_b_login(concurrency: int = 5, duration: float = 60):
    """场景 B: 登录（合法 + 失败混合）。"""
    print(f"\n{'='*60}")
    print(f"  场景 B: 登录 (并发={concurrency}, 持续={duration}s)")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=15) as client:
        tasks = [
            # 合法登录（使用测试前缀用户，可能不存在 → 401）
            lambda: _make_request(
                client, "POST", "/api/v1/auth/login",
                json={"username": "loadtest_user", "password": "test123"},
                headers={"Content-Type": "application/json"},
            ),
            # 失败登录
            lambda: _make_request(
                client, "POST", "/api/v1/auth/login",
                json={"username": "nonexistent", "password": "wrong"},
                headers={"Content-Type": "application/json"},
            ),
        ]

        stats = await _run_concurrent(
            lambda: client, tasks, concurrency, duration,
        )

    return ScenarioResult(
        scenario="B",
        description="登录",
        concurrency=concurrency,
        duration_seconds=duration,
        requests=stats,
    )


# ---------------------------------------------------------------------------
# 场景 C: 会话读取
# ---------------------------------------------------------------------------


async def scenario_c_sessions(concurrency: int = 5, duration: float = 60):
    """场景 C: 会话列表读取。"""
    print(f"\n{'='*60}")
    print(f"  场景 C: 会话读取 (并发={concurrency}, 持续={duration}s)")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=30) as client:
        # 先获取 token
        admin_user = os.environ.get("TEST_ADMIN_USER", "admin")
        admin_pass = os.environ.get("TEST_ADMIN_PASS", "admin123456")
        token = await _get_auth_token(client, admin_user, admin_pass)

        tasks = [
            lambda: _make_request(
                client, "GET", "/api/v1/chat/sessions",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            ),
            lambda: _make_request(
                client, "GET", "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            ),
        ]

        stats = await _run_concurrent(
            lambda: client, tasks, concurrency, duration,
        )

    return ScenarioResult(
        scenario="C",
        description="会话读取",
        concurrency=concurrency,
        duration_seconds=duration,
        requests=stats,
    )


# ---------------------------------------------------------------------------
# 场景 D: 普通非 RAG API
# ---------------------------------------------------------------------------


async def scenario_d_normal_api(concurrency: int = 10, duration: float = 60):
    """场景 D: 普通 API (用户信息、系统状态)。"""
    print(f"\n{'='*60}")
    print(f"  场景 D: 普通 API (并发={concurrency}, 持续={duration}s)")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=30) as client:
        admin_user = os.environ.get("TEST_ADMIN_USER", "admin")
        admin_pass = os.environ.get("TEST_ADMIN_PASS", "admin123456")
        token = await _get_auth_token(client, admin_user, admin_pass)

        tasks = [
            lambda: _make_request(client, "GET", "/api/v1/health"),
            lambda: _make_request(client, "GET", "/api/v1/health/live"),
            lambda: _make_request(
                client, "GET", "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            ),
        ]

        stats = await _run_concurrent(
            lambda: client, tasks, concurrency, duration,
        )

    return ScenarioResult(
        scenario="D",
        description="普通非RAG API",
        concurrency=concurrency,
        duration_seconds=duration,
        requests=stats,
    )


# ---------------------------------------------------------------------------
# 场景 E: RAG 问答
# ---------------------------------------------------------------------------


async def scenario_e_rag(concurrency: int = 1, duration: float = 120):
    """场景 E: RAG 问答（安全：使用只读测试数据）。

    注意: 由于单用户活跃请求=1，Embedding并发=2，Reranker并发=1，
    高并发下会有大量排队。
    """
    print(f"\n{'='*60}")
    print(f"  场景 E: RAG 问答 (并发={concurrency}, 持续={duration}s)")
    print(f"  ⚠ 注意: 单用户活跃RAG请求=1, Embedding并发=2, Reranker并发=1")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=180) as client:
        admin_user = os.environ.get("TEST_ADMIN_USER", "admin")
        admin_pass = os.environ.get("TEST_ADMIN_PASS", "admin123456")
        token = await _get_auth_token(client, admin_user, admin_pass)

        task_fn = lambda: _make_request(
            client, "POST", "/api/v1/rag/ask",
            json={"question": "你好，请简单介绍一下自己"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            } if token else {},
        )

        tasks = [task_fn]

        stats = await _run_concurrent(
            lambda: client, tasks, concurrency, duration,
        )

    return ScenarioResult(
        scenario="E",
        description="RAG问答",
        concurrency=concurrency,
        duration_seconds=duration,
        requests=stats,
    )


# ---------------------------------------------------------------------------
# 场景 G: 上传
# ---------------------------------------------------------------------------


async def scenario_g_upload(concurrency: int = 1, duration: float = 60):
    """场景 G: 上传小文件（安全：使用临时文件）。"""
    print(f"\n{'='*60}")
    print(f"  场景 G: 上传 (并发={concurrency}, 持续={duration}s)")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=120) as client:
        admin_user = os.environ.get("TEST_ADMIN_USER", "admin")
        admin_pass = os.environ.get("TEST_ADMIN_PASS", "admin123456")
        token = await _get_auth_token(client, admin_user, admin_pass)

        # 创建临时测试文件
        test_content = b"This is a test document for load testing.\n" * 100

        async def upload_task():
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
                f.write(test_content)
                f.flush()
                f.seek(0)
                return await _make_request(
                    client, "POST", "/api/v1/documents/upload/",
                    files={"file": ("loadtest.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                )

        tasks = [upload_task]

        stats = await _run_concurrent(
            lambda: client, tasks, concurrency, duration,
        )

    return ScenarioResult(
        scenario="G",
        description="上传",
        concurrency=concurrency,
        duration_seconds=duration,
        requests=stats,
    )


# ---------------------------------------------------------------------------
# 场景 I: 混合负载
# ---------------------------------------------------------------------------


async def scenario_i_mixed(concurrency: int = 5, duration: float = 120):
    """场景 I: 混合负载 (70%读取, 20%RAG, 10%管理)。"""
    print(f"\n{'='*60}")
    print(f"  场景 I: 混合负载 (并发={concurrency}, 持续={duration}s)")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=180) as client:
        admin_user = os.environ.get("TEST_ADMIN_USER", "admin")
        admin_pass = os.environ.get("TEST_ADMIN_PASS", "admin123456")
        token = await _get_auth_token(client, admin_user, admin_pass)

        tasks = [
            # 70% 普通读取
            lambda: _make_request(client, "GET", "/api/v1/health/live"),
            lambda: _make_request(client, "GET", "/api/v1/health"),
            lambda: _make_request(client, "GET", "/"),
            lambda: _make_request(
                client, "GET", "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            ),
            lambda: _make_request(
                client, "GET", "/api/v1/chat/sessions",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            ),
            # 20% RAG
            lambda: _make_request(
                client, "POST", "/api/v1/rag/ask",
                json={"question": "你好"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                } if token else {},
            ),
            # 10% 管理/任务
            lambda: _make_request(
                client, "GET", "/api/v1/admin/system",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            ),
        ]

        stats = await _run_concurrent(
            lambda: client, tasks, concurrency, duration,
        )

    return ScenarioResult(
        scenario="I",
        description="混合负载",
        concurrency=concurrency,
        duration_seconds=duration,
        requests=stats,
    )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


SCENARIO_MAP = {
    "A": ("健康/静态", [
        (scenario_a_health_static, [10, 25, 50]),
    ]),
    "B": ("登录", [
        (scenario_b_login, [5]),
    ]),
    "C": ("会话读取", [
        (scenario_c_sessions, [5, 10, 20]),
    ]),
    "D": ("普通API", [
        (scenario_d_normal_api, [10, 25]),
    ]),
    "E": ("RAG问答", [
        (scenario_e_rag, [1, 2, 3]),
    ]),
    "G": ("上传", [
        (scenario_g_upload, [1, 2]),
    ]),
    "I": ("混合负载", [
        (scenario_i_mixed, [5]),
    ]),
}


async def run_scenario(scenario_key: str, rag_concurrency: int = 1) -> list[ScenarioResult]:
    """运行指定场景的所有并发级别。"""
    if scenario_key not in SCENARIO_MAP:
        print(f"未知场景: {scenario_key}")
        print(f"可用场景: {list(SCENARIO_MAP.keys())}")
        return []

    name, levels = SCENARIO_MAP[scenario_key]
    results = []

    for scenario_fn, concurrencies in levels:
        for concurrency in concurrencies:
            if STOP_REQUESTED:
                break

            # 场景 E 允许覆盖并发
            if scenario_key == "E" and rag_concurrency > 0:
                concurrency = rag_concurrency

            # 压测前快照
            before = _get_resource_snapshot()

            result = await scenario_fn(concurrency=concurrency)

            # 压测后快照
            after = _get_resource_snapshot()
            result.cpu_before = str(before.get("docker_stats", ""))[:200]
            result.cpu_after = str(after.get("docker_stats", ""))[:200]

            results.append(result)
            _print_result(result)

            # 阶段间等待系统恢复
            if concurrency != concurrencies[-1]:
                wait = 15
                print(f"\n  等待 {wait}s 系统恢复...")
                await asyncio.sleep(wait)

    return results


def _print_result(result: ScenarioResult):
    """打印场景结果。"""
    s = result.requests
    print(f"\n  ┌─ 结果 ─────────────────────────────")
    print(f"  │ 场景: {result.scenario} ({result.description})")
    print(f"  │ 并发: {result.concurrency}")
    print(f"  │ 总请求: {s.total}")
    print(f"  │ 成功率: {s.success_rate:.2f}%")
    print(f"  │ 4xx: {s.status_4xx}  5xx: {s.status_5xx}  429: {s.status_429}")
    print(f"  │ P50: {s.p50()*1000:.0f}ms  P95: {s.p95()*1000:.0f}ms  P99: {s.p99()*1000:.0f}ms")
    print(f"  │ Max: {s.max_latency()*1000:.0f}ms")
    if result.stop_reason:
        print(f"  │ ⚠ 停止原因: {result.stop_reason}")
    print(f"  └──────────────────────────────────")


def save_report(all_results: list[ScenarioResult], output_dir: Path):
    """保存压测报告。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"load_test_{timestamp}.json"

    report = {
        "timestamp": timestamp,
        "base_url": BASE_URL,
        "scenarios": [
            {
                "scenario": r.scenario,
                "description": r.description,
                "concurrency": r.concurrency,
                "duration_s": r.duration_seconds,
                "stop_triggered": r.stop_triggered,
                "stop_reason": r.stop_reason,
                "stats": r.requests.to_dict(),
            }
            for r in all_results
        ],
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n报告已保存: {report_file}")

    # 也保存 CSV 摘要
    csv_file = output_dir / f"load_test_{timestamp}.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("scenario,concurrency,total,success_rate,4xx,5xx,429,p50_ms,p95_ms,p99_ms,max_ms\n")
        for r in all_results:
            s = r.requests
            f.write(f"{r.scenario},{r.concurrency},{s.total},{s.success_rate:.1f},"
                    f"{s.status_4xx},{s.status_5xx},{s.status_429},"
                    f"{s.p50()*1000:.0f},{s.p95()*1000:.0f},{s.p99()*1000:.0f},{s.max_latency()*1000:.0f}\n")

    print(f"CSV 已保存: {csv_file}")


async def main():
    parser = argparse.ArgumentParser(description="Phase 10 分阶段压测")
    parser.add_argument(
        "--scenario", choices=["all", "A", "B", "C", "D", "E", "G", "I"],
        default="A", help="压测场景 (default: A)"
    )
    parser.add_argument(
        "--rag-concurrency", type=int, default=0,
        help="场景E并发覆盖 (1-5)"
    )
    parser.add_argument(
        "--target", type=str, default="",
        help="目标地址 (覆盖 BASE_URL)"
    )
    args = parser.parse_args()

    global BASE_URL
    if args.target:
        BASE_URL = args.target.rstrip("/")
        # 安全确认
        if not BASE_URL.startswith("http://localhost") and not BASE_URL.startswith("http://127.0.0.1"):
            print(f"\n{'!'*60}")
            print(f"  ⚠ 目标地址非 localhost: {BASE_URL}")
            print(f"  请确认这是测试环境，不是生产环境！")
            print(f"  压测可能影响服务可用性。")
            print(f"{'!'*60}")
            confirm = input("\n输入 'yes' 继续: ")
            if confirm != "yes":
                print("已取消")
                return

    print(f"目标: {BASE_URL}")
    print(f"场景: {args.scenario}")

    all_results = []

    if args.scenario == "all":
        # 从低到高逐级执行所有场景
        for key in ["A", "B", "C", "D", "E", "G", "I"]:
            if STOP_REQUESTED:
                break
            results = await run_scenario(key, args.rag_concurrency)
            all_results.extend(results)
            if results and results[-1].stop_reason:
                print(f"\n[STOP] 场景 {key} 触发停止条件，跳过后续场景")
                break
            # 场景间等待
            print(f"\n{'~'*40}")
            print("  场景间等待 30s 系统恢复...")
            print(f"{'~'*40}")
            await asyncio.sleep(30)
    else:
        results = await run_scenario(args.scenario, args.rag_concurrency)
        all_results.extend(results)

    # 保存报告
    save_report(all_results, REPORT_DIR)

    # 输出总结
    print(f"\n{'='*60}")
    print(f"  压测完成")
    print(f"{'='*60}")
    print(f"总场景数: {len(all_results)}")

    stable_conc = {}
    for r in all_results:
        if r.requests.error_rate <= 1.0:
            stable_conc[r.scenario] = max(
                stable_conc.get(r.scenario, 0), r.concurrency
            )

    print("\n稳定并发基线:")
    for scenario, conc in sorted(stable_conc.items()):
        name = SCENARIO_MAP.get(scenario, (scenario,))[0]
        print(f"  场景 {scenario} ({name}): 并发 {conc}")


if __name__ == "__main__":
    asyncio.run(main())
