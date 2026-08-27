"""Health check command — fast API and service availability check."""
from __future__ import annotations

import click

from ..common import (
    echo_status,
    echo_section,
    echo_result,
    timestamp,
    http_get,
    API_HEALTH,
    MCP_HOST,
    MCP_PORT,
    check_port,
)


@click.command()
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--mcp", "check_mcp", is_flag=True, help="Also check MCP sidecar")
def health(json_out: bool, check_mcp: bool):
    """🩺 快速健康检查 — API + MCP Sidecar 可用性

    \b
    示例:
      looma health              基本 API 检查
      looma health --mcp        含 MCP Sidecar
      looma health --json       JSON 输出 (CI 友好)
    """
    results = {
        "timestamp": timestamp(),
        "checks": [],
        "all_ok": True,
    }

    echo_section("Looma Health Check")

    # 1. API Health endpoint
    ok, data, err = http_get(API_HEALTH)
    if ok:
        echo_status("ok", f"API Health: {API_HEALTH}")
        results["checks"].append({"name": "api_health", "ok": True, "detail": str(data)})
    else:
        echo_status("error", f"API Health: {API_HEALTH}", f"  → {err}")
        results["checks"].append({"name": "api_health", "ok": False, "error": err})
        results["all_ok"] = False

    # 2. MCP Sidecar (optional)
    if check_mcp:
        if check_port(MCP_HOST, MCP_PORT):
            echo_status("ok", f"MCP Sidecar: {MCP_HOST}:{MCP_PORT}")
            results["checks"].append({"name": "mcp_sidecar", "ok": True})
        else:
            echo_status("warn", f"MCP Sidecar: {MCP_HOST}:{MCP_PORT} not reachable")
            results["checks"].append({"name": "mcp_sidecar", "ok": False})

    # Summary
    echo_section("Summary")
    if results["all_ok"]:
        echo_result("Status", "All checks passed", "ok")
    else:
        echo_result("Status", "Some checks failed", "error")

    if json_out:
        import json
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
