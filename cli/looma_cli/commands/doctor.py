"""Doctor command — comprehensive system diagnostics."""
from __future__ import annotations

import os
from pathlib import Path

import click

from ..common import (
    echo_status,
    echo_section,
    echo_result,
    timestamp,
    http_get,
    http_post,
    check_port,
    check_dns,
    check_sqlite,
    check_process,
    run_local,
    API_HEALTH,
    API_V1,
    MCP_HOST,
    MCP_PORT,
    DEPLOY_TARGETS,
    BACKEND_DIR,
    PROJECT_ROOT,
)


@click.command()
@click.option("--full", is_flag=True, help="Run full diagnostics including SSH checks")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def doctor(full: bool, json_out: bool):
    """🔍 智能诊断 — 全链路健康检查 + 自动问题定位

    \b
    检查范围:
      - DNS 解析
      - API 健康 + 各模块端点
      - ChromaDB 向量库
      - SQLite 数据库完整性
      - MCP Sidecar
      - 本地进程 (gunicorn, chromadb)
      - 磁盘空间 + 内存 (本地)
      - SSH 连接 (--full 模式)

    \b
    示例:
      looma doctor              基础诊断
      looma doctor --full       完整诊断含远程
      looma doctor --json       JSON 输出
    """
    results: dict = {
        "timestamp": timestamp(),
        "sections": {},
        "issues": [],
        "all_ok": True,
    }

    def check(name: str, ok: bool, detail: str = "", critical: bool = False):
        icon = "ok" if ok else ("error" if critical else "warn")
        echo_status(icon, name, f"  → {detail}" if detail and not ok else detail)
        results["sections"][name] = {"ok": ok, "detail": detail}
        if not ok:
            results["issues"].append({"name": name, "detail": detail, "critical": critical})
            if critical:
                results["all_ok"] = False

    click.secho("\n🔍 Looma Doctor — Comprehensive Diagnostics", fg="cyan", bold=True)
    click.secho(f"   Time: {results['timestamp']}\n", fg="bright_black")

    # ── Section 1: Network ──
    echo_section("1. Network & DNS")

    ip = check_dns("api.genz.ltd")
    check("DNS: api.genz.ltd", ip is not None, ip or "resolution failed", critical=True)

    # ── Section 2: API ──
    echo_section("2. API Endpoints")

    ok, data, err = http_get(API_HEALTH)
    check("API Health", ok, str(data) if ok else err, critical=True)

    # Quick endpoint probes
    endpoints = [
        ("/v1/poetry/search?q=春", "Poetry Search"),
        ("/v1/game/personality/questions", "Personality Game"),
    ]
    for path, label in endpoints:
        url = f"{API_V1}{path}" if "?" not in path else f"{API_V1}{path}"
        ok, _, err = http_get(url)
        check(f"Endpoint: {label}", ok, err if not ok else "")

    # ── Section 3: Database ──
    echo_section("3. Database & Storage")

    db_path = BACKEND_DIR / "data" / "looma.db"
    if db_path.exists():
        db_ok, db_result = check_sqlite(db_path)
        check("SQLite Integrity", db_ok, db_result, critical=True)
        db_size = db_path.stat().st_size
        size_str = f"{db_size / 1024 / 1024:.1f} MB"
        echo_status("info", f"Database size: {size_str}")
    else:
        check("SQLite File", False, f"Not found: {db_path}", critical=True)

    # ── Section 4: ChromaDB ──
    echo_section("4. ChromaDB Vector Store")

    chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
    chroma_ok = check_port("127.0.0.1", chroma_port, timeout=3.0)
    check("ChromaDB Port", chroma_ok, f"port {chroma_port} {'open' if chroma_ok else 'closed'}")

    poetry_chroma = BACKEND_DIR / "data" / "poetry_full"
    if poetry_chroma.exists():
        check("Poetry ChromaDB", True, f"{poetry_chroma}")
    else:
        check("Poetry ChromaDB", False, f"Not found: {poetry_chroma}")

    # ── Section 5: MCP Sidecar ──
    echo_section("5. MCP Sidecar")

    mcp_ok = check_port(MCP_HOST, MCP_PORT, timeout=3.0)
    check("MCP Sidecar", mcp_ok, f"{MCP_HOST}:{MCP_PORT} {'reachable' if mcp_ok else 'not reachable'}")

    # ── Section 6: Local Processes ──
    echo_section("6. Local Processes")

    for proc in ["gunicorn", "chroma"]:
        running = check_process(proc)
        check(f"Process: {proc}", running, "running" if running else "not found")

    # ── Section 7: System Resources ──
    echo_section("7. System Resources")

    # Disk
    ok, stdout, _ = run_local(["df", "-h", str(PROJECT_ROOT)])
    if ok:
        lines = stdout.strip().split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 5:
                usage = parts[4]
                disk_ok = int(usage.rstrip("%")) < 90
                check("Disk Usage", disk_ok, usage, critical=not disk_ok)

    # Memory
    ok, stdout, _ = run_local(["vm_stat" if os.uname().sysname == "Darwin" else "free", "-h" if os.uname().sysname != "Darwin" else ""])
    if ok:
        echo_status("info", f"Memory: {stdout.split(chr(10))[0][:80]}")

    # ── Section 8: SSH (--full) ──
    if full:
        echo_section("8. Remote Connectivity (--full)")

        from ..common import ssh_run
        backend = DEPLOY_TARGETS["backend"]
        ok, stdout, stderr = ssh_run(
            backend["host"], backend["user"],
            "systemctl is-active looma-backend 2>/dev/null || echo 'unknown'"
        )
        check("SSH to Backend", ok, stdout or stderr)

        frontend = DEPLOY_TARGETS["frontend"]
        ok, stdout, stderr = ssh_run(
            frontend["host"], frontend["user"],
            "systemctl is-active nginx 2>/dev/null || echo 'unknown'"
        )
        check("SSH to Frontend", ok, stdout or stderr)

    # ── Summary ──
    echo_section("Diagnostic Summary")
    total = len(results["sections"])
    ok_count = sum(1 for v in results["sections"].values() if v["ok"])
    critical_issues = sum(1 for i in results["issues"] if i["critical"])

    if results["all_ok"]:
        echo_result("Result", f"All {total} checks passed", "ok")
    elif critical_issues > 0:
        echo_result("Result", f"{ok_count}/{total} passed, {critical_issues} critical", "error")
    else:
        echo_result("Result", f"{ok_count}/{total} passed, {len(results['issues'])} warnings", "warn")

    if results["issues"]:
        click.echo()
        click.secho("  Issues found:", fg="yellow")
        for issue in results["issues"]:
            tag = "🔴" if issue["critical"] else "🟡"
            click.echo(f"    {tag} {issue['name']}: {issue['detail']}")

    if json_out:
        import json
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
