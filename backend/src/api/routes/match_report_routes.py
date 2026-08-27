"""
Match report routes — persist resume×JD match results.

Endpoints (under /v1/match-reports):
  POST   /                 create report from match results
  GET    /                 list current user's reports
  GET    /:id              report detail with items
  DELETE /:id              soft-delete report
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, g, jsonify, request

from src.api.auth.decorators import require_auth
from src.compliance.audit import AuditLogger
from src.compliance.consent import require_consent
from src.reports.match_report_manager import MatchReportManager

logger = logging.getLogger("looma.match_report_routes")

match_report_bp = Blueprint("match_reports", __name__)


def _manager() -> MatchReportManager:
    return MatchReportManager(current_app._db)


@match_report_bp.route("", methods=["POST"])
@match_report_bp.route("/", methods=["POST"])
@require_auth
@require_consent("jobseeker_core")
def create_match_report():
    body = request.get_json(silent=True) or {}
    matches = body.get("matches")
    if not isinstance(matches, list) or not matches:
        return jsonify(error="bad_request", message="matches 不能为空"), 400

    resume_text = (body.get("resume_text") or "").strip()
    title = (body.get("title") or "").strip()
    summary = (body.get("summary") or "").strip()
    resume_id = (body.get("resume_id") or "").strip()

    try:
        report = _manager().create_report(
            user_id=g.user_id,
            resume_text=resume_text,
            matches=matches,
            title=title,
            summary=summary,
            resume_id=resume_id,
        )
    except ValueError as e:
        return jsonify(error="bad_request", message=str(e)), 400
    except Exception as e:
        logger.exception("create match report failed")
        return jsonify(error="create_failed", message=str(e)), 500

    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_generate",
        resource_type="match_report",
        resource_id=report["id"],
        metadata={"total_jobs": report.get("metadata", {}).get("total_jobs", 0)},
    )

    try:
        from src.timeline.events import record_match_scan
        meta = report.get("metadata") or {}
        if isinstance(meta, str):
            import json
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        record_match_scan(
            current_app._db,
            g.user_id,
            report_id=report["id"],
            total_jobs=int(meta.get("total_jobs") or len(matches)),
            max_score=meta.get("max_score"),
            avg_score=meta.get("avg_score"),
            pipeline_version=str(meta.get("pipeline_version") or ""),
            has_resume_id=bool(resume_id),
        )
    except Exception as e:
        logger.warning("timeline: match_scan skipped for %s: %s", g.user_id, e)

    return jsonify(report), 201


@match_report_bp.route("", methods=["GET"])
@match_report_bp.route("/", methods=["GET"])
@require_auth
def list_match_reports():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    data = _manager().list_user_reports(g.user_id, page=page, page_size=page_size)
    return jsonify(data)


@match_report_bp.route("/<report_id>", methods=["GET"])
@require_auth
def get_match_report(report_id: str):
    report = _manager().get_report(report_id, user_id=g.user_id)
    if not report:
        return jsonify(error="not_found", message="报告不存在"), 404
    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_view",
        resource_type="match_report",
        resource_id=report_id,
    )
    return jsonify(report)


@match_report_bp.route("/<report_id>/export", methods=["GET"])
@require_auth
def export_match_report(report_id: str):
    """Export full report JSON (user data sovereignty)."""
    report = _manager().get_report(report_id, user_id=g.user_id)
    if not report:
        return jsonify(error="not_found", message="报告不存在"), 404
    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_export",
        resource_type="match_report",
        resource_id=report_id,
        metadata={"format": "json"},
    )
    return jsonify(report)


@match_report_bp.route("/<report_id>/share", methods=["POST"])
@require_auth
@require_consent("report_share")
def share_match_report(report_id: str):
    """Grant career_partner access to selected dimensions (mid-term slice)."""
    body = request.get_json(silent=True) or {}
    dimensions = body.get("shared_dimensions") or []
    if not isinstance(dimensions, list) or not dimensions:
        return jsonify(error="bad_request", message="shared_dimensions 不能为空"), 400
    purpose = (body.get("purpose") or "").strip()
    shared_with_id = (body.get("shared_with_id") or "").strip()
    try:
        sharing = _manager().share_report(
            report_id=report_id,
            user_id=g.user_id,
            shared_dimensions=dimensions,
            purpose=purpose,
            shared_with_type="career_partner",
            shared_with_id=shared_with_id,
            expires_at=body.get("expires_at"),
        )
    except ValueError as e:
        code = str(e)
        if code == "not_found":
            return jsonify(error="not_found", message="报告不存在"), 404
        return jsonify(error="bad_request", message=code), 400
    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_share_grant",
        resource_type="report_sharing",
        resource_id=sharing["id"],
        metadata={"report_id": report_id, "dimensions": dimensions},
    )
    return jsonify(sharing), 201


@match_report_bp.route("/<report_id>/share/<sharing_id>", methods=["PUT"])
@require_auth
def update_match_report_share(report_id: str, sharing_id: str):
    body = request.get_json(silent=True) or {}
    dimensions = body.get("shared_dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return jsonify(error="bad_request", message="shared_dimensions 不能为空"), 400
    try:
        sharing = _manager().update_sharing(
            sharing_id=sharing_id,
            user_id=g.user_id,
            report_id=report_id,
            shared_dimensions=dimensions,
        )
    except ValueError as e:
        if str(e) == "not_found":
            return jsonify(error="not_found", message="授权记录不存在"), 404
        return jsonify(error="bad_request", message=str(e)), 400
    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_share_update",
        resource_type="report_sharing",
        resource_id=sharing_id,
        metadata={"dimensions": dimensions},
    )
    return jsonify(sharing)


@match_report_bp.route("/<report_id>/share/<sharing_id>", methods=["DELETE"])
@require_auth
def revoke_match_report_share(report_id: str, sharing_id: str):
    try:
        sharing = _manager().revoke_sharing(
            sharing_id=sharing_id,
            user_id=g.user_id,
            report_id=report_id,
        )
    except ValueError as e:
        if str(e) == "not_found":
            return jsonify(error="not_found", message="授权记录不存在"), 404
        return jsonify(error="bad_request", message=str(e)), 400
    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_share_revoke",
        resource_type="report_sharing",
        resource_id=sharing_id,
    )
    return jsonify(sharing)


@match_report_bp.route("/<report_id>/sharings", methods=["GET"])
@require_auth
def list_match_report_sharings(report_id: str):
    try:
        rows = _manager().list_sharings(report_id=report_id, user_id=g.user_id)
    except ValueError as e:
        if str(e) == "not_found":
            return jsonify(error="not_found", message="报告不存在"), 404
        return jsonify(error="bad_request", message=str(e)), 400
    return jsonify(sharings=rows)


@match_report_bp.route("/maintenance/purge", methods=["POST"])
@require_auth
def purge_deleted_match_reports():
    """Physically delete soft-deleted reports older than N days (admin only)."""
    if getattr(g, "user_role", None) != "admin":
        return jsonify(error="forbidden", message="仅管理员可执行清理"), 403
    body = request.get_json(silent=True) or {}
    days = int(body.get("days") or 30)
    result = _manager().purge_deleted(days=days)
    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_purge",
        resource_type="match_report",
        metadata=result,
    )
    return jsonify(result)


@match_report_bp.route("/<report_id>", methods=["DELETE"])
@require_auth
def delete_match_report(report_id: str):
    ok = _manager().delete_report(report_id, user_id=g.user_id)
    if not ok:
        return jsonify(error="not_found", message="报告不存在"), 404
    AuditLogger().log_from_request(
        actor=g.user_id,
        action="report_delete",
        resource_type="match_report",
        resource_id=report_id,
    )
    return jsonify(ok=True, id=report_id)
