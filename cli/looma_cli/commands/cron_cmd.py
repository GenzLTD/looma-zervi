"""Cron command — scheduled health checks and monitoring."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from ..common import (
    echo_status,
    echo_section,
    echo_result,
    timestamp,
    http_get,
    check_port,
    API_HEALTH,
    MCP_HOST,
    MCP_PORT,
    DEPLOY_TARGETS,
)

CRON_STORE = Path.home() / ".looma" / "cron_jobs.json"


def _load_jobs() -> list[dict]:
    if CRON_STORE.exists():
        try:
            return json.loads(CRON_STORE.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save_jobs(jobs: list[dict]):
    CRON_STORE.parent.mkdir(parents=True, exist_ok=True)
    CRON_STORE.write_text(json.dumps(jobs, indent=2))


@click.group()
def cron():
    """⏰ 定时监控 — 自动化健康检查与告警

    \b
    子命令:
      add      添加定时任务
      list     查看所有任务
      run      立即运行一次
      remove   删除任务
      start    启动后台调度器

    \b
    示例:
      looma cron add --name "health-check" --interval 300
      looma cron list
      looma cron run --name "health-check"
    """
    pass


@cron.command()
@click.option("--name", required=True, help="任务名称")
@click.option("--interval", type=int, default=300, help="执行间隔（秒），默认 300")
@click.option("--check", type=click.Choice(["health", "status", "all"]), default="health", help="检查类型")
@click.option("--alert", is_flag=True, help="异常时输出告警")
def add(name: str, interval: int, check: str, alert: bool):
    """添加定时监控任务

    \b
    示例:
      looma cron add --name "api-monitor" --interval 600 --check health --alert
      looma cron add --name "full-check" --interval 3600 --check all
    """
    jobs = _load_jobs()

    if any(j["name"] == name for j in jobs):
        click.secho(f"  ⚠ Task '{name}' already exists. Remove it first.", fg="yellow")
        return

    job = {
        "name": name,
        "interval": interval,
        "check": check,
        "alert": alert,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
    }
    jobs.append(job)
    _save_jobs(jobs)

    echo_status("ok", f"Task added: {name}")
    click.echo(f"    Interval: {interval}s | Check: {check} | Alert: {alert}")


@cron.command()
def list():
    """查看所有定时监控任务"""
    jobs = _load_jobs()
    if not jobs:
        click.secho("  No cron jobs configured.", fg="bright_black")
        click.echo("  Use 'looma cron add' to create one.")
        return

    echo_section("Scheduled Monitoring Tasks")
    for j in jobs:
        status_icon = "✅" if j.get("enabled", True) else "⏸️"
        alert_icon = "🔔" if j.get("alert") else "🔕"
        click.echo(f"  {status_icon} {alert_icon} {j['name']}")
        click.secho(f"     Interval: {j['interval']}s | Check: {j['check']}", fg="bright_black")


@cron.command()
@click.option("--name", required=True, help="任务名称")
def run(name: str):
    """立即执行一次定时任务"""
    jobs = _load_jobs()
    job = next((j for j in jobs if j["name"] == name), None)
    if not job:
        click.secho(f"  ❌ Task not found: {name}", fg="red")
        return

    echo_section(f"Running: {name}")

    checks_ok = True

    # API Health
    echo_status("pending", "API Health ...")
    ok, data, err = http_get(API_HEALTH)
    if ok:
        echo_status("ok", "API healthy")
    else:
        echo_status("error", f"API unhealthy: {err}")
        checks_ok = False

    # Backend port
    backend = DEPLOY_TARGETS["backend"]
    echo_status("pending", f"Backend {backend['host']}:{backend['port']} ...")
    if check_port(backend["host"], backend["port"], timeout=5.0):
        echo_status("ok", "Backend reachable")
    else:
        echo_status("warn", "Backend unreachable")
        checks_ok = False

    # MCP
    if job["check"] in ("status", "all"):
        echo_status("pending", f"MCP {MCP_HOST}:{MCP_PORT} ...")
        if check_port(MCP_HOST, MCP_PORT, timeout=3.0):
            echo_status("ok", "MCP reachable")
        else:
            echo_status("warn", "MCP unreachable")

    if checks_ok:
        echo_result("Result", "All checks passed", "ok")
    else:
        echo_result("Result", "Issues detected", "warn")
        if job.get("alert"):
            click.secho(f"\n  🔔 ALERT: {name} detected issues at {timestamp()}", fg="red", bold=True)


@cron.command()
@click.option("--name", required=True, help="任务名称")
def remove(name: str):
    """删除定时任务"""
    jobs = _load_jobs()
    new_jobs = [j for j in jobs if j["name"] != name]
    if len(new_jobs) == len(jobs):
        click.secho(f"  ❌ Task not found: {name}", fg="red")
        return
    _save_jobs(new_jobs)
    echo_status("ok", f"Removed: {name}")


@cron.command()
@click.option("--daemon", is_flag=True, help="后台运行（前台阻塞）")
def start(daemon: bool):
    """启动定时监控调度器

    \b
    looma cron start           前台运行一次
    looma cron start --daemon  后台持续运行
    """
    jobs = _load_jobs()
    if not jobs:
        click.secho("  No cron jobs. Use 'looma cron add' first.", fg="yellow")
        return

    click.secho(f"\n⏰ Looma Cron Scheduler — {len(jobs)} jobs", fg="cyan", bold=True)
    click.secho(f"   Press Ctrl+C to stop\n", fg="bright_black")

    try:
        while True:
            for job in jobs:
                if not job.get("enabled", True):
                    continue
                ctx = click.Context(run)
                ctx.invoke(run, name=job["name"])
                click.echo()

            if not daemon:
                break

            # Find the shortest interval to wait
            min_interval = min(j["interval"] for j in jobs if j.get("enabled", True))
            click.secho(f"  Next run in {min_interval}s ...", fg="bright_black")
            time.sleep(min_interval)

    except KeyboardInterrupt:
        click.echo()
        click.secho("  Scheduler stopped.", fg="yellow")
