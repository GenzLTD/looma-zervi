"""
Looma CLI — Main entry point.

A unified CLI tool for the Looma-Zervi career growth platform:
deployment, diagnostics, credit checks, and scheduled monitoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the CLI can find looma backend modules
BACKEND_SRC = Path(__file__).resolve().parent.parent.parent / "backend" / "src"
if BACKEND_SRC.exists():
    sys.path.insert(0, str(BACKEND_SRC))

import click

from .commands.deploy import deploy
from .commands.doctor import doctor
from .commands.status_cmd import status
from .commands.health import health
from .commands.credit_cmd import credit
from .commands.cron_cmd import cron
from .commands.auth_cmd import login, logout, whoami


@click.group()
@click.version_option(version="1.0.0", prog_name="looma")
@click.pass_context
def main(ctx: click.Context):
    """🛸 Looma CLI — 职业成长平台的运维大脑

    一站式管理 Looma-Zervi 的部署、诊断、征信查询和定时监控。

    \b
    快速开始:
      looma doctor         全面诊断系统健康状态
      looma status         查看系统运行状态
      looma credit 腾讯    查询企业征信
      looma health         快速健康检查
    """
    ctx.ensure_object(dict)


# Register command groups
main.add_command(deploy)
main.add_command(doctor)
main.add_command(status)
main.add_command(health)
main.add_command(credit)
main.add_command(cron)
main.add_command(login)
main.add_command(logout)
main.add_command(whoami)


if __name__ == "__main__":
    main()
