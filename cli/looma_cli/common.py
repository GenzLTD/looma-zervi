"""Common utilities for Looma CLI commands."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

import click

# ── Configuration ───────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_SRC = BACKEND_DIR / "src"

# Deployment targets (from CURRENT_SYSTEM_ARCHITECTURE.md)
DEPLOY_TARGETS = {
    "backend": {
        "host": os.getenv("LOOMA_BACKEND_HOST", "1.14.202.161"),
        "user": os.getenv("LOOMA_BACKEND_USER", "root"),
        "path": os.getenv("LOOMA_BACKEND_PATH", "/root/looma-zervi/backend"),
        "port": int(os.getenv("LOOMA_BACKEND_PORT", "5200")),
        "service": os.getenv("LOOMA_BACKEND_SERVICE", "looma-backend"),
    },
    "frontend": {
        "host": os.getenv("LOOMA_FRONTEND_HOST", "47.115.168.107"),
        "user": os.getenv("LOOMA_FRONTEND_USER", "root"),
        "path": os.getenv("LOOMA_FRONTEND_PATH", "/var/www/looma-frontend"),
    },
}

# API endpoints
API_BASE = os.getenv("LOOMA_API_BASE", "http://api.genz.ltd")
API_HEALTH = f"{API_BASE}/health"
API_V1 = f"{API_BASE}/v1"
MCP_PORT = int(os.getenv("MCP_PORT", "8999"))
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")

# Timeouts
HTTP_TIMEOUT = 10  # seconds
SSH_TIMEOUT = 30  # seconds


# ── Display helpers ─────────────────────────────────────────────────────────

STATUS_ICONS = {
    "ok": "✅",
    "warn": "⚠️",
    "error": "❌",
    "pending": "⏳",
    "info": "ℹ️",
    "skip": "⏭️",
}

COLORS = {
    "ok": "green",
    "warn": "yellow",
    "error": "red",
    "info": "blue",
    "dim": "bright_black",
}


def echo_status(status: str, message: str, detail: str = ""):
    """Print a status line with icon and optional detail."""
    icon = STATUS_ICONS.get(status, "•")
    color = COLORS.get(status, None)
    click.secho(f"  {icon} ", nl=False, fg=color)
    click.echo(message, nl=False)
    if detail:
        click.secho(f"  {detail}", fg="bright_black")
    else:
        click.echo()


def echo_section(title: str):
    """Print a section header."""
    click.echo()
    click.secho(f"── {title} ", fg="cyan", bold=True)


def echo_result(title: str, value: str, status: str = "ok"):
    """Print a key-value result line."""
    icon = STATUS_ICONS.get(status, "  ")
    click.secho(f"  {icon} {title}: ", nl=False, fg=COLORS.get(status))
    click.echo(value)


def timestamp() -> str:
    """Return ISO 8601 timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── HTTP helpers ────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = HTTP_TIMEOUT) -> tuple[bool, Any, str]:
    """Perform HTTP GET request. Returns (ok, data, error_msg)."""
    try:
        req = Request(url, headers={"User-Agent": "Looma-CLI/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {"raw": body}
            return resp.status == 200, data, ""
    except URLError as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, str(e)


def qcc_rpc(service: str, method: str, params: dict | None = None, timeout: int = 30) -> tuple[bool, Any, str]:
    """Call QCC MCP JSON-RPC endpoint directly (bypasses looma API auth).
    
    Uses the QCC_AUTH_TOKEN from environment or default config.
    Returns (ok, data, error_msg).
    """
    try:
        from urllib.request import Request, urlopen
        
        QCC_URLS = {
            "company": "https://agent.qcc.com/mcp/company/stream",
            "risk": "https://agent.qcc.com/mcp/risk/stream",
            "operation": "https://agent.qcc.com/mcp/operation/stream",
            "executive": "https://agent.qcc.com/mcp/executive/stream",
        }
        
        url = QCC_URLS.get(service)
        if not url:
            return False, None, f"Unknown QCC service: {service}"
        
        qcc_token = os.getenv("QCC_AUTH_TOKEN", "")
        
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }).encode("utf-8")
        
        req = Request(url, data=payload, headers={
            "Authorization": qcc_token,
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        })
        
        with urlopen(req, timeout=timeout) as resp:
            # QCC SSE responses don't declare charset; force UTF-8 decode
            raw = resp.read()
            text = raw.decode("utf-8")
            for line in text.split("\n"):
                if line.startswith("data: "):
                    return True, json.loads(line[6:]), ""
            return True, {"raw": text}, ""
            
    except URLError as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, str(e)


def http_post(url: str, payload: dict, timeout: int = HTTP_TIMEOUT) -> tuple[bool, Any, str]:
    """Perform HTTP POST request. Returns (ok, data, error_msg)."""
    try:
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Looma-CLI/1.0",
            },
            method="POST",
        )
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status in (200, 201), data, ""
    except URLError as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, str(e)


# ── Network helpers ─────────────────────────────────────────────────────────

def check_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """Check if a TCP port is open."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_dns(hostname: str) -> Optional[str]:
    """Resolve hostname to IP. Returns IP or None."""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


# ── SSH helpers ─────────────────────────────────────────────────────────────

def ssh_run(host: str, user: str, command: str, timeout: int = SSH_TIMEOUT) -> tuple[bool, str, str]:
    """Run a command via SSH. Returns (ok, stdout, stderr)."""
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", f"ServerAliveInterval={timeout}",
        f"{user}@{host}",
        command,
    ]
    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "SSH connection timed out"
    except FileNotFoundError:
        return False, "", "ssh command not found"


def scp_upload(local_path: Path, host: str, user: str, remote_path: str) -> tuple[bool, str]:
    """Upload a file via SCP. Returns (ok, error_msg)."""
    cmd = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        str(local_path),
        f"{user}@{host}:{remote_path}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0, result.stderr.strip()
    except Exception as e:
        return False, str(e)


# ── Local process helpers ───────────────────────────────────────────────────

def run_local(cmd: list[str], timeout: int = 30) -> tuple[bool, str, str]:
    """Run a local command. Returns (ok, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"


def check_process(name: str) -> bool:
    """Check if a process is running locally."""
    ok, stdout, _ = run_local(["pgrep", "-f", name])
    return ok and bool(stdout.strip())


# ── Database helpers ────────────────────────────────────────────────────────

def check_sqlite(db_path: Path) -> tuple[bool, str]:
    """Check SQLite database integrity."""
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()
        return result == "ok", str(result)
    except Exception as e:
        return False, str(e)


# ── Progress spinner ────────────────────────────────────────────────────────

class Spinner:
    """Simple CLI spinner for long operations."""

    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = ""):
        self.message = message
        self._running = False

    def __enter__(self):
        self._running = True
        click.echo(f"  {self.message} ", nl=False)
        return self

    def __exit__(self, *args):
        self._running = False
        click.echo()

    def update(self, message: str):
        self.message = message
