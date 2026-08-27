"""Status command — full system status overview."""
from __future__ import annotations

import click

from ..common import (
    echo_status,
    echo_section,
    echo_result,
    timestamp,
    http_get,
    check_port,
    check_dns,
    API_HEALTH,
    API_V1,
    DEPLOY_TARGETS,
)


@click.command()
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def status(json_out: bool):
    """📊 系统运行状态 — 全链路健康概览

    \b
    检查范围:
      - DNS 解析 (api.genz.ltd)
      - 后端 API 健康
      - 后端端口可达性
      - 前端服务器可达性

    \b
    示例:
      looma status
      looma status --json
    """
    results: dict = {
        "timestamp": timestamp(),
        "dns": {},
        "api": {},
        "backend": {},
        "frontend": {},
    }

    echo_section("Looma System Status")
    click.secho(f"  Time: {results['timestamp']}", fg="bright_black")
    click.echo()

    # 1. DNS
    echo_status("pending", "DNS Resolution ...")
    ip = check_dns("api.genz.ltd")
    if ip:
        echo_status("ok", f"api.genz.ltd → {ip}")
        results["dns"] = {"ok": True, "ip": ip}
    else:
        echo_status("error", "api.genz.ltd — DNS resolution failed")
        results["dns"] = {"ok": False}

    # 2. API Health
    echo_status("pending", "API Health ...")
    ok, data, err = http_get(API_HEALTH)
    if ok:
        echo_status("ok", f"API healthy: {API_HEALTH}")
        results["api"] = {"ok": True, "detail": str(data)}
    else:
        echo_status("error", f"API unhealthy: {err}")
        results["api"] = {"ok": False, "error": err}

    # 3. Backend port
    backend = DEPLOY_TARGETS["backend"]
    echo_status("pending", f"Backend port {backend['host']}:{backend['port']} ...")
    if check_port(backend["host"], backend["port"], timeout=5.0):
        echo_status("ok", f"Backend reachable: {backend['host']}:{backend['port']}")
        results["backend"]["port"] = True
    else:
        echo_status("warn", f"Backend port closed: {backend['host']}:{backend['port']}")
        results["backend"]["port"] = False

    # 4. Frontend
    frontend = DEPLOY_TARGETS["frontend"]
    echo_status("pending", f"Frontend {frontend['host']}:80 ...")
    if check_port(frontend["host"], 80, timeout=5.0):
        echo_status("ok", f"Frontend reachable: {frontend['host']}:80")
        results["frontend"]["port"] = True
    else:
        echo_status("warn", f"Frontend port closed: {frontend['host']}:80")
        results["frontend"]["port"] = False

    # Summary
    echo_section("Summary")
    all_ok = all(
        results.get(k, {}).get("ok", results.get(k, {}).get("port", False))
        for k in ["dns", "api"]
    )
    if all_ok:
        echo_result("Overall", "System operational", "ok")
    else:
        echo_result("Overall", "Issues detected", "warn")

    if json_out:
        import json
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
