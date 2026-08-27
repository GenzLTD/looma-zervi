"""
Career Timeline API — /v1/timeline/*

See docs/TIMELINE_EVENT_MODEL.md and contracts/timeline.v1.json.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from src.api.auth.decorators import require_auth
from src.timeline.constants import EVENT_KIND_MANUAL
from src.timeline.events import (
    compute_growth_stub,
    sanitize_payload,
    serialize_timeline_row,
)

logger = logging.getLogger("looma.timeline_routes")

timeline_bp = Blueprint("timeline", __name__)


def _get_db():
    return current_app._db


def _error(msg: str, code: str, status: int = 400):
    return jsonify(error=code, message=msg), status


@timeline_bp.route("", methods=["GET"])
@timeline_bp.route("/", methods=["GET"])
@require_auth
def list_timeline():
    """List current user's career timeline (newest first)."""
    db = _get_db()
    kind = (request.args.get("kind") or "").strip() or None
    since = (request.args.get("since") or "").strip() or None
    cursor = (request.args.get("cursor") or "").strip() or None
    try:
        limit = int(request.args.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50

    rows = db.list_timeline_events(
        g.user_id,
        event_kind=kind,
        since=since,
        cursor=cursor,
        limit=limit,
    )
    items = [serialize_timeline_row(r) for r in rows]
    next_cursor = items[-1]["occurred_at"] if len(items) >= limit else None
    return jsonify(items=items, next_cursor=next_cursor, count=len(items))


@timeline_bp.route("/events", methods=["POST"])
@require_auth
def create_timeline_event():
    """Manual write: project_record / check_in / career_decision only."""
    data = request.get_json() or {}
    event_kind = (data.get("event_kind") or "").strip()
    if event_kind not in EVENT_KIND_MANUAL:
        return _error(
            f"manual write only allows: {', '.join(sorted(EVENT_KIND_MANUAL))}",
            "invalid_event_kind",
        )

    title = (data.get("title") or "").strip()
    summary = (data.get("summary") or "").strip()
    payload = sanitize_payload(data.get("payload") if isinstance(data.get("payload"), dict) else {})
    occurred_at = (data.get("occurred_at") or "").strip() or None
    visibility = (data.get("visibility") or "private").strip()

    db = _get_db()
    row = db.insert_timeline_event(
        user_id=g.user_id,
        event_kind=event_kind,
        source_system="manual",
        source_ref=(data.get("source_ref") or "").strip(),
        title=title or event_kind,
        summary=summary,
        payload=payload,
        signal_quality="self_report",
        confidence=0.45,
        weight_role="evidence",
        visibility=visibility if visibility in ("private", "l1", "l2", "l3") else "private",
        occurred_at=occurred_at,
        allow_duplicate=(event_kind == "check_in"),
    )
    return jsonify(serialize_timeline_row(row)), 201


@timeline_bp.route("/events/<event_id>", methods=["PATCH"])
@require_auth
def patch_timeline_event(event_id: str):
    """Supersede with corrected title/summary/payload."""
    data = request.get_json() or {}
    db = _get_db()
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else None
    if payload is not None:
        payload = sanitize_payload(payload)
    new_row = db.supersede_timeline_event(
        g.user_id,
        event_id,
        title=data.get("title"),
        summary=data.get("summary"),
        payload=payload,
    )
    if not new_row:
        return _error("event not found", "not_found", 404)
    return jsonify(serialize_timeline_row(new_row))


@timeline_bp.route("/events/<event_id>", methods=["DELETE"])
@require_auth
def delete_timeline_event(event_id: str):
    db = _get_db()
    ok = db.soft_delete_timeline_event(g.user_id, event_id)
    if not ok:
        return _error("event not found", "not_found", 404)
    return jsonify(ok=True, id=event_id)


@timeline_bp.route("/growth", methods=["GET"])
@require_auth
def get_growth():
    """Minimal growth curve — honest low confidence when sparse."""
    db = _get_db()
    return jsonify(compute_growth_stub(db, g.user_id))


@timeline_bp.route("/bridge/backfill", methods=["POST"])
@require_auth
def bridge_backfill():
    """Idempotent: project quiz / share / match / resume into timeline."""
    from src.timeline.events import backfill_user_timeline

    db = _get_db()
    written = backfill_user_timeline(db, g.user_id)
    count = db.count_timeline_events(g.user_id)
    return jsonify(
        ok=True,
        written_kinds=written,
        event_count=count,
        note="backfill: quiz + account_joined + missions + share/invite + match_reports + resume",
    )


@timeline_bp.route("/export", methods=["GET"])
@require_auth
def export_my_data():
    """GDPR: export all active timeline events + growth as machine-readable JSON.

    Returns a self-contained file the user can download and take to another platform.
    """
    db = _get_db()
    # list_timeline_events caps limit at 100 — page with cursor for a full export
    rows: list = []
    cursor = None
    while True:
        batch = db.list_timeline_events(g.user_id, limit=100, cursor=cursor)
        if not batch:
            break
        rows.extend(batch)
        cursor = batch[-1].get("occurred_at")
        if len(batch) < 100 or not cursor:
            break
    active = [r for r in rows if r.get("status") == "active"]
    items = [serialize_timeline_row(r) for r in active]

    # Append growth summary as metadata
    from src.timeline.events import build_timeline_l1_summary

    summary = build_timeline_l1_summary(db, g.user_id)

    return jsonify(
        exported_at=datetime.now(timezone.utc).isoformat(),
        user_id=g.user_id,
        event_count=len(items),
        l1_summary=summary,
        items=items,
        note="This is your complete PlanetX career timeline. You own this data.",
    )


@timeline_bp.route("/me", methods=["DELETE"])
@require_auth
def delete_all_my_events():
    """GDPR: soft-delete every timeline event owned by the authenticated user.

    Requires explicit confirmation via ?confirm=yes query param to prevent accidents.
    """
    confirm = (request.args.get("confirm") or "").strip().lower()
    if confirm != "yes":
        return jsonify(
            error="confirmation_required",
            message="添加 ?confirm=yes 以确认删除所有时间线数据。此操作不可撤销。",
            hint="GET /v1/timeline/export first to download your data.",
        ), 400

    db = _get_db()
    total = db.count_timeline_events(g.user_id)
    deleted = 0
    errors = 0

    # Batch soft-delete in pages of 100
    while True:
        batch = db.list_timeline_events(g.user_id, limit=100)
        if not batch:
            break
        for row in batch:
            try:
                db.soft_delete_timeline_event(g.user_id, row["id"])
                deleted += 1
            except Exception:
                errors += 1
        if len(batch) < 100:
            break

    logger.info(
        "GDPR delete_timeline user=%s total=%d deleted=%d errors=%d",
        g.user_id, total, deleted, errors,
    )

    return jsonify(
        ok=True,
        user_id=g.user_id,
        deleted=deleted,
        errors=errors,
        total_was=total,
        note="Timeline data has been soft-deleted. Growth curves will be empty until new events accumulate.",
    )
