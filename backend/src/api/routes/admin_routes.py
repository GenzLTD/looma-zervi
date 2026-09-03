"""
Admin dashboard routes — aggregated stats for admin panel.
Ownership: Jason

Endpoints:
  GET  /v1/admin/stats        - Full admin dashboard metrics (users, activity, system)
  GET  /v1/admin/funnel       - Funnel conversion stats
  GET  /v1/admin/narrative    - Narrative/Phase 0 metrics
  GET  /v1/admin/health       - Enhanced system health (admin view)
"""
import logging
import time
import os
import sys
import platform

from flask import Blueprint, request, jsonify, current_app, g, render_template

from src.api.auth.decorators import require_auth

logger = logging.getLogger("looma.admin")

admin_bp = Blueprint("admin", __name__)


def _require_admin():
    """Check that the current user is an admin; return error response or None."""
    if g.get("user_role") != "admin":
        return jsonify(error="forbidden", message="admin only"), 403
    return None


def _get_db():
    return current_app._db


# ── Full admin stats ──

@admin_bp.route("/admin/stats", methods=["GET"])
@require_auth
def admin_stats():
    """Aggregated admin dashboard metrics."""
    err = _require_admin()
    if err:
        return err

    db = _get_db()
    stats = db.get_admin_stats()
    return jsonify(stats)


# ── Funnel stats ──

@admin_bp.route("/admin/funnel", methods=["GET"])
@require_auth
def admin_funnel():
    """Funnel conversion stats with configurable time window."""
    err = _require_admin()
    if err:
        return err

    days = int(request.args.get("days", 30))
    days = max(1, min(days, 90))
    db = _get_db()
    stats = db.get_funnel_stats(days=days)
    return jsonify(stats)


# ── Narrative / Phase 0 metrics ──

@admin_bp.route("/admin/narrative", methods=["GET"])
@require_auth
def admin_narrative():
    """Aggregated Phase 0 narrative metrics."""
    err = _require_admin()
    if err:
        return err

    db = _get_db()
    stats = db.get_narrative_stats()
    return jsonify(stats)


# ── Enhanced health check (admin only) ──

@admin_bp.route("/admin/health", methods=["GET"])
@require_auth
def admin_health():
    """Enhanced system health with DB stats, Python version, uptime."""
    err = _require_admin()
    if err:
        return err

    db = _get_db()

    # DB stats
    with db.get_conn() as conn:
        try:
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            db_size_mb = round((page_count * page_size) / (1024 * 1024), 2)
        except Exception:
            db_size_mb = 0

        try:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        except Exception:
            journal_mode = "unknown"

        # Table counts
        tables = {}
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall():
            tname = row["name"]
            try:
                cnt = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM [{tname}]"
                ).fetchone()["cnt"]
            except Exception:
                cnt = -1
            tables[tname] = cnt

    # Config info
    config = current_app.config
    env = config.get("FLASK_ENV", config.get("ENV", "unknown"))

    # LLM provider from config/env
    llm_provider = os.environ.get("LLM_PROVIDER", config.get("LLM_PROVIDER", "unknown"))
    embedding_model = os.environ.get("EMBEDDING_MODEL", config.get("EMBEDDING_MODEL", "unknown"))

    # Process uptime
    try:
        proc_start = os.stat("/proc/1/cmdline").st_ctime if os.path.exists("/proc/1/cmdline") else 0
    except Exception:
        proc_start = 0

    return jsonify({
        "status": "ok",
        "service": "looma-backend",
        "environment": env,
        "python": {
            "version": sys.version,
            "executable": sys.executable,
        },
        "platform": platform.platform(),
        "database": {
            "size_mb": db_size_mb,
            "journal_mode": journal_mode,
            "table_counts": tables,
        },
        "llm": {
            "provider": llm_provider,
            "embedding_model": embedding_model,
        },
        "process": {
            "pid": os.getpid(),
            "start_time": proc_start if proc_start else None,
        },
    })


# ── LLM 运维面 (ServBay 风格三件套：依赖卡片 + 模型适配清单 + 24h 仪表) ──

def _require_admin_manual():
    """JWT + admin role check for routes that must NOT run @require_auth
    (the HTML shell must be openable without a token; data stays protected)."""
    from src.api.auth.jwt_handler import verify_token

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify(error="unauthorized", message="Missing or invalid Authorization header"), 401
    try:
        payload = verify_token(auth_header[7:])
    except Exception as e:
        return jsonify(error="unauthorized", message=f"Invalid token: {str(e)}"), 401
    db = _get_db()
    user = db.get_user_by_id(payload["sub"]) if db else None
    if not user:
        return jsonify(error="unauthorized", message="user not found"), 401
    if user.get("role") != "admin":
        return jsonify(error="forbidden", message="admin only"), 403
    return None


def _llm_providers_probe():
    """Probe LLM providers in LLM_PROVIDER_ORDER (shape matches app._collect_dependencies)."""
    from src.app import _probe_base

    config = current_app.config
    order = [
        p.strip().lower()
        for p in (config.get("LLM_PROVIDER_ORDER") or os.getenv("LLM_PROVIDER_ORDER") or "deepseek").split(",")
        if p.strip()
    ]
    out = []
    for p in order:
        if p == "deepseek":
            key = (config.get("DEEPSEEK_API_KEY") or "").strip()
            base = config.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
            model = config.get("DEEPSEEK_MODEL") or "deepseek-chat"
        elif p == "openai":
            key = (config.get("OPENAI_API_KEY") or "").strip()
            base = config.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
            model = config.get("OPENAI_MODEL") or "gpt-3.5-turbo"
        elif p == "ollama":
            key = "local"
            base = config.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
            model = config.get("OLLAMA_MODEL") or "qwen2.5-coder:1.5b"
        else:
            out.append({"name": p, "base": "", "model": "", "status": "unknown", "cls": "bad"})
            continue
        if key and key.lower() not in ("skip", "your-deepseek-api-key", "your-openai-api-key"):
            status = _probe_base(base, key if p != "ollama" else "")
        else:
            status = "not_configured"
        cls = {"ok": "ok", "not_configured": "muted", "unreachable": "bad"}.get(status, "warn")
        out.append({"name": p, "base": base, "model": model, "status": status, "cls": cls})
    return out


@admin_bp.route("/admin/llm-ops", methods=["GET"])
def admin_llm_ops():
    """LLM 运维面：
    - 默认返回 JSON 数据（require JWT + admin role）
    - ?view=page 返回页面壳（无数据；页面 JS 带 token 拉取本端点数据并自动刷新）
    """
    from datetime import datetime

    if request.args.get("view") in ("1", "page", "html"):
        return render_template(
            "llm-ops.html",
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    err = _require_admin_manual()
    if err:
        return err

    db = _get_db()
    hours = max(1, min(int(request.args.get("hours", 24) or 24), 168))
    from src.agents.llm_catalog import LLM_MODEL_CATALOG
    from src.app import _qcc_gateway_status

    return jsonify({
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hours": hours,
        "deps": _llm_providers_probe(),
        "qcc": _qcc_gateway_status(),
        "catalog": LLM_MODEL_CATALOG,
        "stats": db.get_llm_usage_stats(hours=hours),
    })
