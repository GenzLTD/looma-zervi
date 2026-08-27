"""Deploy command — one-click deployment to production servers."""
from __future__ import annotations

import click

from ..common import (
    echo_status,
    echo_section,
    echo_result,
    ssh_run,
    scp_upload,
    run_local,
    DEPLOY_TARGETS,
    BACKEND_DIR,
    PROJECT_ROOT,
)


@click.group()
def deploy():
    """🚀 一键部署 — 前后端生产环境部署

    \b
    子命令:
      backend   部署后端到生产服务器
      frontend  部署前端到生产服务器
      all       全量部署
      check     部署前检查
    """
    pass


@deploy.command()
@click.option("--restart/--no-restart", default=True, help="部署后重启服务")
@click.option("--dry-run", is_flag=True, help="仅显示将要执行的命令")
def backend(restart: bool, dry_run: bool):
    """部署后端到生产服务器

    \b
    流程:
      1. 拉取最新代码
      2. 安装 Python 依赖
      3. 重启 gunicorn 服务
      4. 健康检查验证

    \b
    示例:
      looma deploy backend
      looma deploy backend --dry-run
      looma deploy backend --no-restart
    """
    target = DEPLOY_TARGETS["backend"]
    host, user, path, service = target["host"], target["user"], target["path"], target["service"]

    echo_section(f"Deploy Backend → {user}@{host}")

    commands = [
        (f"cd {path} && git pull origin main", "Git pull"),
        (f"cd {path} && source venv/bin/activate && pip install -r requirements.txt -q", "Install deps"),
    ]
    if restart:
        commands.append((f"systemctl restart {service}", f"Restart {service}"))
        commands.append(("sleep 3 && systemctl is-active " + service, "Verify service"))

    for cmd, desc in commands:
        if dry_run:
            echo_status("pending", f"[DRY RUN] {desc}", f"  ssh {user}@{host} '{cmd}'")
        else:
            echo_status("pending", f"{desc} ...")
            ok, stdout, stderr = ssh_run(host, user, cmd)
            if ok:
                echo_status("ok", desc, stdout[:100] if stdout else "")
            else:
                echo_status("error", desc, stderr[:200] if stderr else "failed")
                click.secho(f"  ⚠ Deployment may have issues. Check server logs.", fg="yellow")
                break

    # Final health check
    if not dry_run and restart:
        echo_section("Health Check")
        ok, stdout, _ = ssh_run(host, user, f"curl -sf http://localhost:{target['port']}/health && echo OK")
        if ok and "OK" in stdout:
            echo_result("Backend", "Deployed successfully", "ok")
        else:
            echo_result("Backend", "Health check failed", "warn")


@deploy.command()
@click.option("--dry-run", is_flag=True, help="仅显示将要执行的命令")
def frontend(dry_run: bool):
    """部署前端到生产服务器

    \b
    流程:
      1. 本地构建前端 (pnpm build)
      2. 上传 dist 到服务器
      3. 重载 Nginx

    \b
    示例:
      looma deploy frontend
      looma deploy frontend --dry-run
    """
    target = DEPLOY_TARGETS["frontend"]
    host, user, path = target["host"], target["user"], target["path"]
    frontend_dir = PROJECT_ROOT / "frontend"

    echo_section(f"Deploy Frontend → {user}@{host}")

    # Step 1: Build locally
    echo_status("pending", "Building frontend ...")
    if not dry_run:
        ok, stdout, stderr = run_local(
            ["pnpm", "run", "build:prod"],
            timeout=120,
            cwd=str(frontend_dir)
        )
        if ok:
            echo_status("ok", "Build succeeded")
        else:
            echo_status("error", "Build failed", stderr[:200])
            return
    else:
        echo_status("pending", "[DRY RUN] pnpm run build:prod")

    # Step 2: Upload
    dist_dir = frontend_dir / "packages" / "saas" / "dist"
    if not dist_dir.exists():
        echo_status("error", f"Dist directory not found: {dist_dir}")
        return

    echo_status("pending", "Uploading to server ...")
    if not dry_run:
        ok, err = scp_upload(dist_dir, host, user, path)
        if ok:
            echo_status("ok", "Upload succeeded")
        else:
            echo_status("error", f"Upload failed: {err}")
            return
    else:
        echo_status("pending", f"[DRY RUN] scp {dist_dir} → {user}@{host}:{path}")

    # Step 3: Reload nginx
    echo_status("pending", "Reloading Nginx ...")
    if not dry_run:
        ok, stdout, stderr = ssh_run(host, user, "systemctl reload nginx")
        if ok:
            echo_status("ok", "Nginx reloaded")
        else:
            echo_status("error", f"Nginx reload failed: {stderr}")
    else:
        echo_status("pending", "[DRY RUN] systemctl reload nginx")

    echo_section("Result")
    echo_result("Frontend", "Deployed successfully" if not dry_run else "Dry run complete", "ok")


@deploy.command()
@click.option("--restart/--no-restart", default=True, help="部署后重启服务")
@click.option("--dry-run", is_flag=True, help="仅显示将要执行的命令")
@click.pass_context
def all(ctx: click.Context, restart: bool, dry_run: bool):
    """全量部署 — 后端 + 前端一键部署

    \b
    示例:
      looma deploy all
      looma deploy all --dry-run
    """
    echo_section("🚀 Full Deployment — Backend + Frontend")

    ctx.invoke(backend, restart=restart, dry_run=dry_run)
    click.echo()
    ctx.invoke(frontend, dry_run=dry_run)

    echo_section("Deployment Complete")


@deploy.command()
def check():
    """部署前检查 — 验证部署条件

    \b
    检查项:
      - SSH 连接性
      - 目标路径存在
      - 服务状态
    """
    echo_section("Pre-deployment Check")

    for name, target in DEPLOY_TARGETS.items():
        echo_status("pending", f"Checking {name} ({target['host']}) ...")
        ok, stdout, stderr = ssh_run(
            target["host"], target["user"],
            f"ls {target['path']} > /dev/null 2>&1 && echo OK || echo MISSING"
        )
        if ok and "OK" in stdout:
            echo_status("ok", f"{name}: SSH OK, path exists")
        elif ok and "MISSING" in stdout:
            echo_status("warn", f"{name}: SSH OK, path missing: {target['path']}")
        else:
            echo_status("error", f"{name}: SSH failed: {stderr}")

    echo_result("Pre-check", "Complete — review warnings above", "ok")
