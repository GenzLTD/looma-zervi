"""
CLI auth — login and token management for calling looma backend APIs.

Token is stored at ~/.looma/auth.json and used by credit_cmd to
auto-report credit check records to the trust layer.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from ..common import API_BASE, http_post

TOKEN_DIR = Path.home() / ".looma"
TOKEN_FILE = TOKEN_DIR / "auth.json"


def _ensure_token_dir():
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)


def save_token(token_data: dict):
    """Persist token to ~/.looma/auth.json."""
    _ensure_token_dir()
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2, ensure_ascii=False))
    TOKEN_FILE.chmod(0o600)


def load_token() -> dict | None:
    """Load persisted token. Returns None if missing or expired."""
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    # Simple expiry check: if we have an expires_at timestamp
    import time
    expires = data.get("expires_at", 0)
    if expires and time.time() > expires:
        return None
    return data


def get_auth_header() -> str | None:
    """Get Authorization header value for API calls, or None if not logged in."""
    token_data = load_token()
    if not token_data:
        return None
    return f"Bearer {token_data['access_token']}"


def is_logged_in() -> bool:
    """Check if CLI has a valid auth token."""
    return get_auth_header() is not None


@click.command()
@click.option("--email", prompt="Email", help="注册邮箱")
@click.option("--password", prompt="密码", hide_input=True, help="登录密码")
def login(email: str, password: str):
    """🔑 登录 Looma — 获取 API Token（用于征信查询自动上报）

    登录后 Token 保存在 ~/.looma/auth.json，credit 命令会自动使用它
    将征信查询记录上报到信任层长期记忆体。

    \b
    示例:
      looma login                     # 交互式输入邮箱和密码
      looma login --email a@b.com     # 命令行指定邮箱
    """
    click.secho("🛸 Looma CLI — 登录", bold=True)
    click.echo()

    url = f"{API_BASE}/v1/auth/login"
    ok, data, err = http_post(url, {"email": email.strip(), "password": password})

    if not ok:
        click.secho(f"  ❌ 登录失败: {err or data.get('message', '未知错误')}", fg="red")
        sys.exit(1)

    import time
    expires_in = data.get("expires_in", 86400)
    token_data = {
        "access_token": data["access_token"],
        "token_type": data.get("token_type", "bearer"),
        "expires_at": int(time.time()) + expires_in - 300,  # 5 min buffer
        "user": data.get("user", {}),
    }

    save_token(token_data)

    user = data.get("user", {})
    click.secho(f"  ✅ 登录成功！", fg="green")
    click.secho(f"  👤 {user.get('email', '?')} (tier: {user.get('tier', 'free')})", fg="bright_black")
    click.secho(f"  📁 Token 已保存至 {TOKEN_FILE}", fg="bright_black")
    click.echo()
    click.secho("  提示: 现在 looma credit 命令会自动上报查询记录到信任层", fg="bright_black")


@click.command()
def logout():
    """登出 — 清除本地保存的 API Token"""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        click.secho("✅ 已登出，Token 已清除", fg="green")
    else:
        click.secho("ℹ️ 当前未登录", fg="bright_black")


@click.command()
def whoami():
    """查看当前登录状态"""
    token_data = load_token()
    if not token_data:
        click.secho("❌ 未登录 — 使用 looma login 登录", fg="yellow")
        return

    user = token_data.get("user", {})
    import time
    remaining = max(0, token_data.get("expires_at", 0) - int(time.time()))
    hours = remaining // 3600
    mins = (remaining % 3600) // 60

    click.secho("✅ 已登录", fg="green")
    click.secho(f"  👤 {user.get('email', '?')}", fg="bright_black")
    click.secho(f"  ⭐ Tier: {user.get('tier', 'free')}", fg="bright_black")
    click.secho(f"  ⏰ Token 剩余: {hours}h {mins}m", fg="bright_black")
