"""
Analytics routes — product events, micro feedback, funnel stats.
Ownership: Jason (内测闭环埋点)

Endpoints:
  POST /v1/analytics/events   - Batch log product events (optional_auth)
  GET  /v1/analytics/funnel     - Funnel summary (require_auth)
  POST /v1/feedback/micro      - Contextual micro feedback (optional_auth)
"""
from __future__ import annotations

import logging

from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth, optional_auth

logger = logging.getLogger("looma.analytics")

analytics_bp = Blueprint("analytics", __name__)

VALID_EVENTS = frozenset({
    "quiz_complete",
    "share_code_created",
    "share_link_copied",
    "profile_view_public",
    "profile_view_failed",
    "hr_register_from_share",
    "candidate_imported",
    "candidate_import_duplicate",
    "trial_started",
    "trial_failed",
    "trial_clicked",
    "tier_activated",
    "funnel_drop",
})

VALID_FEEDBACK_CONTEXTS = frozenset({
    "planetx_result",
    "tspace_profile_share",
    "tspace_pricing",
})


def _db():
    return current_app._db


@analytics_bp.route("/analytics/events", methods=["POST"])
@optional_auth
def log_events():
    """Batch ingest product events from Web / miniprogram clients."""
    data = request.get_json() or {}
    events = data.get("events") or []
    if not isinstance(events, list) or not events:
        return jsonify(error="bad_request", message="events array required"), 400
    if len(events) > 50:
        return jsonify(error="bad_request", message="max 50 events per batch"), 400

    user_id = g.get("user_id") if getattr(g, "user_id", None) else None
    normalized = []
    for ev in events:
        name = (ev.get("event_name") or "").strip()
        if name not in VALID_EVENTS:
            return jsonify(error="bad_request", message=f"unknown event_name: {name}"), 400
        normalized.append({
            "event_name": name,
            "user_id": ev.get("user_id") or user_id,
            "session_id": ev.get("session_id"),
            "platform": ev.get("platform") or "unknown",
            "share_code": ev.get("share_code"),
            "source": "client",
            "success": ev.get("success", True),
            "properties": ev.get("properties"),
        })

    count = _db().log_product_events_batch(normalized)
    return jsonify(ok=True, ingested=count)


@analytics_bp.route("/analytics/funnel", methods=["GET"])
@require_auth
def funnel_stats():
    """Closed-loop funnel aggregates for internal beta review."""
    days = int(request.args.get("days", 30))
    days = max(1, min(days, 90))
    stats = _db().get_funnel_stats(days=days)
    return jsonify(stats)


@analytics_bp.route("/feedback/micro", methods=["POST"])
@optional_auth
def micro_feedback():
    """Submit one-question contextual feedback (👍/👎 or 1–5)."""
    data = request.get_json() or {}
    context = (data.get("context") or "").strip()
    score = data.get("score")

    if context not in VALID_FEEDBACK_CONTEXTS:
        return jsonify(error="bad_request", message=f"invalid context: {context}"), 400
    if score is None or not isinstance(score, int) or score < 0 or score > 5:
        return jsonify(error="bad_request", message="score must be 0–5"), 400

    optional_text = (data.get("optional_text") or "")[:500] or None
    user_id = g.get("user_id") if getattr(g, "user_id", None) else data.get("user_id")

    fid = _db().submit_micro_feedback(
        context=context,
        score=score,
        optional_text=optional_text,
        user_id=user_id,
        session_id=data.get("session_id"),
        platform=data.get("platform") or "unknown",
        share_code=data.get("share_code"),
    )
    return jsonify(ok=True, id=fid), 201
