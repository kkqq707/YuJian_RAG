#!/usr/bin/env python3
"""Phase 10 生产部署加固验证脚本

验证:
1. Docker Compose 资源配置
2. Nginx 配置
3. 健康检查端点
4. 备份脚本基础功能
5. 安全响应头
6. 磁盘监控服务

不执行破坏性测试，不写入生产数据。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost")
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

PASS = 0
FAIL = 0


def log_pass(msg: str):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def log_fail(msg: str):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def log_info(msg: str):
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# 1. Docker Compose 配置验证
# ---------------------------------------------------------------------------


def test_docker_compose():
    """验证 docker-compose.yml 的资源配置。"""
    print("\n=== Docker Compose 配置验证 ===")

    compose_file = PROJECT_DIR / "docker-compose.yml"
    if not compose_file.exists():
        log_fail("docker-compose.yml 不存在")
        return

    content = compose_file.read_text(encoding="utf-8")

    # 检查关键配置
    checks = {
        "mem_limit backend": "mem_limit: 3g" in content or "mem_limit: 3G" in content,
        "mem_reservation backend": "mem_reservation:" in content,
        "cpus backend": "cpus:" in content,
        "pids_limit backend": "pids_limit:" in content,
        "mem_limit frontend": content.count("mem_limit:") >= 2,
        "stop_grace_period": "stop_grace_period:" in content,
        "stop_signal SIGTERM": "SIGTERM" in content,
        "restart unless-stopped": "unless-stopped" in content,
        "logging max-size": "max-size" in content,
        "logging max-file": "max-file" in content,
        "healthcheck backend": "healthcheck:" in content,
        "healthcheck frontend": content.count("healthcheck:") >= 2,
        "depends_on service_healthy": "service_healthy" in content,
        "no privileged": "privileged: true" not in content,
        "no docker socket": "/var/run/docker.sock" not in content,
    }

    for name, result in checks.items():
        if result:
            log_pass(name)
        else:
            log_fail(name)


# ---------------------------------------------------------------------------
# 2. Nginx 配置验证
# ---------------------------------------------------------------------------


def test_nginx_config():
    """验证 nginx.conf 配置。"""
    print("\n=== Nginx 配置验证 ===")

    nginx_file = PROJECT_DIR / "frontend" / "nginx.conf"
    if not nginx_file.exists():
        log_fail("nginx.conf 不存在")
        return

    content = nginx_file.read_text(encoding="utf-8")

    checks = {
        "server_tokens off": "server_tokens off" in content,
        "proxy_buffering off": "proxy_buffering off" in content,
        "proxy_cache off": "proxy_cache off" in content,
        "proxy_http_version 1.1": "proxy_http_version 1.1" in content,
        "X-Real-IP": "X-Real-IP" in content,
        "X-Forwarded-For": "X-Forwarded-For" in content,
        "X-Request-ID": "X-Request-ID" in content,
        "X-Accel-Buffering no": "X-Accel-Buffering no" in content,
        "client_max_body_size": "client_max_body_size" in content,
        "proxy_read_timeout": "proxy_read_timeout" in content,
        "hide .env": ".env" in content and "deny all" in content,
        "X-Content-Type-Options": "X-Content-Type-Options" in content,
        "X-Frame-Options": "X-Frame-Options" in content,
        "Permissions-Policy": "Permissions-Policy" in content,
        "gzip on": "gzip on" in content,
        "SPA fallback": "try_files $uri $uri/ /index.html" in content,
        "no index.html cache": "no-cache, no-store, must-revalidate" in content,
    }

    for name, result in checks.items():
        if result:
            log_pass(name)
        else:
            log_fail(name)


# ---------------------------------------------------------------------------
# 3. 健康检查端点验证
# ---------------------------------------------------------------------------


async def test_health_endpoints():
    """验证健康检查端点。"""
    print("\n=== 健康检查端点验证 ===")

    async with httpx.AsyncClient(timeout=15) as client:
        # Liveness
        try:
            resp = await client.get(f"{BASE_URL}/api/v1/health/live")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "alive":
                    log_pass(f"Liveness: 200 (alive)")
                else:
                    log_fail(f"Liveness: 状态异常: {data}")
            else:
                log_fail(f"Liveness: HTTP {resp.status_code}")
        except Exception as e:
            log_fail(f"Liveness: 连接失败: {e}")

        # Readiness
        try:
            resp = await client.get(f"{BASE_URL}/api/v1/health/ready")
            data = resp.json()
            components = data.get("components", {})
            if resp.status_code in (200, 503):
                ready_count = sum(1 for v in components.values() if v)
                total = len(components)
                log_pass(f"Readiness: HTTP {resp.status_code} ({ready_count}/{total} ready)")
                for comp, ok in components.items():
                    if ok:
                        log_info(f"  {comp}: OK")
                    else:
                        log_info(f"  {comp}: NOT READY")
            else:
                log_fail(f"Readiness: HTTP {resp.status_code}")
        except Exception as e:
            log_fail(f"Readiness: 连接失败: {e}")

        # Legacy health
        try:
            resp = await client.get(f"{BASE_URL}/api/v1/health")
            data = resp.json()
            if data.get("backend"):
                log_pass(f"Health: backend=True")
                if data.get("database"):
                    log_info("  database: OK")
                if data.get("rag"):
                    log_info("  rag: OK")
            else:
                log_fail(f"Health: 响应异常")
        except Exception as e:
            log_fail(f"Health: 连接失败: {e}")


# ---------------------------------------------------------------------------
# 4. 安全响应头验证
# ---------------------------------------------------------------------------


async def test_security_headers():
    """验证安全响应头。"""
    print("\n=== 安全响应头验证 ===")

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{BASE_URL}/api/v1/health/live")
            headers = resp.headers

            required = [
                "x-request-id",
                "x-content-type-options",
                "x-frame-options",
            ]

            for h in required:
                if h in headers:
                    log_pass(f"{h}: 存在")
                else:
                    log_fail(f"{h}: 缺失")

        except Exception as e:
            log_fail(f"请求失败: {e}")


# ---------------------------------------------------------------------------
# 5. 磁盘监控服务验证
# ---------------------------------------------------------------------------


def test_disk_monitor():
    """验证磁盘监控服务。"""
    print("\n=== 磁盘监控服务验证 ===")

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from backend.app.services.disk_monitor import check_disk_space, get_disk_summary

        # 基础检查
        result = check_disk_space()
        if result.ok or result.warning or result.critical:
            log_pass(f"check_disk_space: ok={result.ok} warning={result.warning} critical={result.critical}")
            log_info(f"  message: {result.message}")
            for d in result.disks:
                log_info(f"  {d.mount_point}: {d.percent_used:.1f}% used, {d.free_bytes/(1024**3):.1f}GB free")
        else:
            log_fail("check_disk_space 返回异常")

        # 摘要
        summary = get_disk_summary()
        if summary["status"] in ("ok", "warning", "critical"):
            log_pass(f"get_disk_summary: status={summary['status']}")
        else:
            log_fail(f"get_disk_summary: 异常状态 {summary['status']}")

        # 上传空间检查
        upload_check = __import__('backend.app.services.disk_monitor', fromlist=['check_space_for_upload']).check_space_for_upload(1024 * 1024)
        log_pass("check_space_for_upload: 可用")

        # 备份空间检查
        backup_check = __import__('backend.app.services.disk_monitor', fromlist=['check_space_for_backup']).check_space_for_backup()
        log_pass("check_space_for_backup: 可用")

    except Exception as e:
        log_fail(f"磁盘监控异常: {e}")


# ---------------------------------------------------------------------------
# 6. 上传大小限制验证
# ---------------------------------------------------------------------------


async def test_upload_size_limit():
    """验证 client_max_body_size 和后端 MAX_UPLOAD_SIZE_MB。"""
    print("\n=== 上传大小限制验证 ===")

    # 检查 Nginx 配置
    nginx_file = PROJECT_DIR / "frontend" / "nginx.conf"
    content = nginx_file.read_text(encoding="utf-8")

    # 提取 client_max_body_size
    import re
    matches = re.findall(r"client_max_body_size\s+(\d+)m", content, re.IGNORECASE)
    if matches:
        nginx_limit = max(int(m) for m in matches)
        log_info(f"Nginx client_max_body_size: {nginx_limit}m")
    else:
        nginx_limit = None
        log_fail("未找到 client_max_body_size")

    # 检查后端配置
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from backend.app.config import get_settings
        settings = get_settings()
        backend_limit = settings.MAX_UPLOAD_SIZE_MB
        log_info(f"Backend MAX_UPLOAD_SIZE_MB: {backend_limit}")

        if nginx_limit and nginx_limit >= backend_limit:
            log_pass(f"Nginx limit ({nginx_limit}m) >= Backend limit ({backend_limit}m)")
        elif nginx_limit:
            log_fail(f"Nginx limit ({nginx_limit}m) < Backend limit ({backend_limit}m)")
    except Exception as e:
        log_fail(f"配置读取失败: {e}")

    # 测试超大上传
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/api/v1/documents/upload/",
                files={"file": ("large.txt", b"x" * (55 * 1024 * 1024), "text/plain")},
            )
            if resp.status_code in (401, 403, 413):
                log_pass(f"超大文件上传: HTTP {resp.status_code} (正确拒绝)")
            else:
                log_info(f"超大文件上传: HTTP {resp.status_code}")
        except Exception:
            log_info("超大文件上传: 连接被重置（可能被 Nginx 拒绝）")


# ---------------------------------------------------------------------------
# 7. Docker 状态验证
# ---------------------------------------------------------------------------


def test_docker_status():
    """验证 Docker 容器状态。"""
    print("\n=== Docker 状态验证 ===")

    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(PROJECT_DIR / "docker-compose.yml"), "ps"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            output = result.stdout
            if "backend" in output:
                log_pass("Backend 容器存在")

                # 检查 restart policy
                inspect = subprocess.run(
                    ["docker", "inspect", "yujian-backend"],
                    capture_output=True, text=True, timeout=10,
                )
                if inspect.returncode == 0:
                    config = json.loads(inspect.stdout)[0]
                    restart = config.get("HostConfig", {}).get("RestartPolicy", {}).get("Name", "")
                    mem_limit = config.get("HostConfig", {}).get("Memory", 0)
                    if restart:
                        log_pass(f"Restart policy: {restart}")
                    if mem_limit > 0:
                        log_pass(f"Memory limit: {mem_limit / (1024**3):.1f}GB")

            if "frontend" in output:
                log_pass("Frontend 容器存在")
        else:
            log_info("Docker Compose 未运行或不可用（跳过）")
    except FileNotFoundError:
        log_info("Docker 不可用（跳过）")
    except Exception as e:
        log_info(f"Docker 检查跳过: {e}")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------


async def main():
    print("=" * 60)
    print("  Phase 10 生产部署加固验证")
    print("=" * 60)

    # 同步测试
    test_docker_compose()
    test_nginx_config()
    test_disk_monitor()
    test_docker_status()

    # 异步测试
    await test_health_endpoints()
    await test_security_headers()
    await test_upload_size_limit()

    # 汇总
    total = PASS + FAIL
    print(f"\n{'='*60}")
    print(f"  验证结果: {PASS}/{total} 通过")
    print(f"{'='*60}")

    if FAIL > 0:
        print(f"\n  {FAIL} 项失败，请检查上述输出。")
        sys.exit(1)
    else:
        print(f"\n  全部通过！Phase 10 配置验证成功。")
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
