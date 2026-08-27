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

from flask import Blueprint, request, jsonify, current_app, g

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
