"""
Enterprise routes blueprint (T空间 B-end).
Ownership: szbenyx

Endpoints:
  POST /v1/enterprise/create              - Create an enterprise
  POST /v1/enterprise/join                - Join an enterprise
  GET  /v1/enterprise/profile             - Get enterprise profile
  GET  /v1/enterprise/candidates          - List candidates for enterprise
  GET  /v1/enterprise/candidate/<id>      - Get candidate detail (HR profile view)
  POST /v1/enterprise/candidates/add      - Add a candidate manually
  POST /v1/enterprise/candidates/import-share - Import candidate from PlanetX share code
  POST /v1/enterprise/contact-sales       - Submit enterprise sales inquiry
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth, require_tier, optional_auth
from src.analytics.events import (
    log_product_event,
    platform_from_request,
    EVENT_CANDIDATE_IMPORTED,
    EVENT_CANDIDATE_IMPORT_DUPLICATE,
)
from src.utils.tier_limits import get_candidate_limit, is_at_limit
from src.db.manager import DatabaseManager

logger = logging.getLogger("looma.enterprise")

enterprise_bp = Blueprint("enterprise", __name__)

PROFILE_SHARE_GRANT = "profile_share"


def _get_user_enterprise(conn, user_id: str):
    """Return (enterprise_id, role) or None."""
    row = conn.execute(
        "SELECT enterprise_id, role FROM enterprise_users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def _parse_profile_data(raw) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _candidate_response(row: dict) -> dict:
    result = dict(row)
    result["profile_data"] = _parse_profile_data(result.get("profile_data"))
    return result


def _candidate_capacity_error(tier: str, current: int):
    limit = get_candidate_limit(tier)
    if limit == 0:
        return jsonify(
            error="forbidden",
            message="需要升级至支持者版才能管理候选人",
            upgrade={"tier": "supporter"},
        ), 403
    return jsonify(
        error="quota_exceeded",
        message=f"候选人池已达上限（{limit}人），请升级套餐",
        limit=limit,
        current=current,
        upgrade={"tier": "pro" if tier == "supporter" else "enterprise"},
    ), 429


def _check_candidate_capacity(conn, enterprise_id: str, tier: str):
    limit = get_candidate_limit(tier)
    if limit == 0:
        return _candidate_capacity_error(tier, 0)
    if limit is not None:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM candidates WHERE enterprise_id = ?",
            (enterprise_id,),
        ).fetchone()["cnt"]
        if is_at_limit(count, tier, resource="candidate"):
            return _candidate_capacity_error(tier, count)
    return None


@enterprise_bp.route("/create", methods=["POST"])
@require_auth
def create_enterprise():
    """Create a new enterprise (HR company/training org)."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    domain = data.get("domain", "").strip()

    if not name:
        return jsonify(error="bad_request", message="enterprise name required"), 400

    db = current_app._db
    enterprise_id = str(uuid.uuid4())

    try:
        with db.get_conn() as conn:
            conn.execute(
                """INSERT INTO enterprises (id, name, domain)
                   VALUES (?, ?, ?)""",
                (enterprise_id, name, domain)
            )
            # Creator becomes admin
            conn.execute(
                """INSERT INTO enterprise_users (id, enterprise_id, user_id, role)
                   VALUES (?, ?, ?, 'admin')""",
                (str(uuid.uuid4()), enterprise_id, g.user_id)
            )
        return jsonify(id=enterprise_id, name=name, domain=domain, role="admin"), 201
    except Exception as e:
        return jsonify(error="create_failed", message=str(e)), 500


@enterprise_bp.route("/join", methods=["POST"])
@require_auth
def join_enterprise():
    """Join an existing enterprise as member."""
    data = request.get_json() or {}
    enterprise_id = data.get("enterprise_id", "").strip()

    if not enterprise_id:
        return jsonify(error="bad_request", message="enterprise_id required"), 400

    db = current_app._db

    try:
        with db.get_conn() as conn:
            # Check enterprise exists
            row = conn.execute("SELECT id FROM enterprises WHERE id = ?", (enterprise_id,)).fetchone()
            if not row:
                return jsonify(error="not_found", message="企业不存在"), 404

            # Check not already a member
            existing = conn.execute(
                "SELECT id FROM enterprise_users WHERE enterprise_id = ? AND user_id = ?",
                (enterprise_id, g.user_id)
            ).fetchone()
            if existing:
                return jsonify(error="conflict", message="已经是该企业的成员"), 409

            conn.execute(
                """INSERT INTO enterprise_users (id, enterprise_id, user_id, role)
                   VALUES (?, ?, ?, 'member')""",
                (str(uuid.uuid4()), enterprise_id, g.user_id)
            )
        return jsonify(enterprise_id=enterprise_id, role="member")
    except Exception as e:
        return jsonify(error="join_failed", message=str(e)), 500


@enterprise_bp.route("/profile", methods=["GET"])
@require_auth
def enterprise_profile():
    """Get the enterprise the current user belongs to."""
    db = current_app._db

    try:
        with db.get_conn() as conn:
            row = conn.execute(
                """SELECT e.*, eu.role FROM enterprises e
                   JOIN enterprise_users eu ON e.id = eu.enterprise_id
                   WHERE eu.user_id = ?""",
                (g.user_id,)
            ).fetchone()

        if not row:
            return jsonify(error="not_found", message="不属于任何企业"), 404

        result = dict(row)
        return jsonify(result)
    except Exception as e:
        return jsonify(error="profile_failed", message=str(e)), 500


@enterprise_bp.route("/candidates", methods=["GET"])
@require_auth
@require_tier("supporter")
def list_candidates():
    """List candidates for the current user's enterprise."""
    db = current_app._db
    tier = g.user_tier
    limit = get_candidate_limit(tier)

    try:
        with db.get_conn() as conn:
            eu_row = conn.execute(
                "SELECT enterprise_id, role FROM enterprise_users WHERE user_id = ?",
                (g.user_id,)
            ).fetchone()

            if not eu_row:
                return jsonify(error="not_found", message="不属于任何企业"), 404

            enterprise_id = dict(eu_row)["enterprise_id"]

            query = (
                "SELECT * FROM candidates WHERE enterprise_id = ? "
                "ORDER BY created_at DESC"
            )
            if limit is not None:
                query += f" LIMIT {limit}"

            rows = conn.execute(query, (enterprise_id,)).fetchall()
            total = db.count_enterprise_candidates(enterprise_id)

        return jsonify(
            candidates=[_candidate_response(dict(r)) for r in rows],
            limit=limit,
            total=total,
        )
    except Exception as e:
        return jsonify(error="list_failed", message=str(e)), 500


@enterprise_bp.route("/candidate/<candidate_id>", methods=["GET"])
@require_auth
@require_tier("supporter")
def get_candidate(candidate_id: str):
    """Get a single candidate with full profile data (HR view)."""
    db = current_app._db

    try:
        with db.get_conn() as conn:
            eu = _get_user_enterprise(conn, g.user_id)
            if not eu:
                return jsonify(error="not_found", message="不属于任何企业"), 404

            row = conn.execute(
                "SELECT * FROM candidates WHERE id = ? AND enterprise_id = ?",
                (candidate_id, eu["enterprise_id"]),
            ).fetchone()

            if not row:
                return jsonify(error="not_found", message="候选人不存在"), 404

            result = _candidate_response(dict(row))

            # ── Trust Bridge: attach trust profile for HR view ──
            candidate_user_id = result.get("user_id")
            if candidate_user_id:
                try:
                    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
                    trust_db = DatabaseManager(db_path)
                    attestations = trust_db.get_trust_attestations(candidate_user_id)
                    result["trust_profile"] = {
                        "attestations": attestations,
                        "total": len(attestations),
                    }
                except Exception as e:
                    logger.warning("trust_bridge: HR trust profile failed for %s: %s", candidate_user_id, e)

                try:
                    from src.timeline.events import build_timeline_l1_summary
                    result["timeline_l1"] = build_timeline_l1_summary(db, candidate_user_id)
                except Exception as e:
                    logger.warning("timeline_l1: HR summary failed for %s: %s", candidate_user_id, e)
                    result["timeline_l1"] = {
                        "level": "l1",
                        "event_count": 0,
                        "has_thickness": False,
                        "confidence": "empty",
                        "message": "尚无足够行为沉淀，画像厚度不足",
                        "recent_labels": [],
                    }

        return jsonify(result)
    except Exception as e:
        return jsonify(error="get_failed", message=str(e)), 500


@enterprise_bp.route("/candidates/import-share", methods=["POST"])
@require_auth
@require_tier("supporter")
def import_candidate_from_share():
    """Import a PlanetX job seeker into the enterprise via profile share code."""
    data = request.get_json() or {}
    share_code = data.get("share_code", "").strip().upper()

    if not share_code:
        return jsonify(error="bad_request", message="share_code required"), 400

    db = current_app._db

    try:
        with db.get_conn() as conn:
            eu = _get_user_enterprise(conn, g.user_id)
            if not eu:
                return jsonify(error="not_found", message="请先创建或加入企业"), 404

            enterprise_id = eu["enterprise_id"]

            blocked = _check_candidate_capacity(conn, enterprise_id, g.user_tier)
            if blocked:
                return blocked

            invite = conn.execute(
                "SELECT * FROM invite_codes WHERE code = ? AND tier_grant = ?",
                (share_code, PROFILE_SHARE_GRANT),
            ).fetchone()
            if not invite:
                return jsonify(error="not_found", message="分享码无效"), 404

            invite = dict(invite)
            seeker_id = invite["created_by"]

            # Avoid duplicate import
            existing = conn.execute(
                """SELECT id FROM candidates
                   WHERE enterprise_id = ? AND user_id = ?""",
                (enterprise_id, seeker_id),
            ).fetchone()
            if existing:
                row = conn.execute(
                    "SELECT * FROM candidates WHERE id = ?",
                    (dict(existing)["id"],),
                ).fetchone()
                result = _candidate_response(dict(row))
                result["imported"] = False
                log_product_event(
                    db,
                    EVENT_CANDIDATE_IMPORT_DUPLICATE,
                    user_id=g.user_id,
                    share_code=share_code,
                    platform=platform_from_request(request),
                    source="server",
                )
                return jsonify(result), 200

            user_row = conn.execute(
                "SELECT id, name, email FROM users WHERE id = ?",
                (seeker_id,),
            ).fetchone()
            profile_row = conn.execute(
                "SELECT * FROM game_profiles WHERE user_id = ?",
                (seeker_id,),
            ).fetchone()

            if not profile_row:
                return jsonify(error="not_found", message="该求职者尚未完成人格测试"), 404

            user = dict(user_row) if user_row else {}
            profile = dict(profile_row)
            display_name = user.get("name") or user.get("email") or "求职者"
            if display_name and "@" in display_name:
                display_name = display_name.split("@")[0]

            detail = profile.get("personality_detail")
            profile_data = {
                "personality_type": profile.get("personality_type"),
                "personality_detail": _parse_profile_data(detail) or detail,
                "xp": profile.get("xp", 0),
                "level": profile.get("level", 1),
                "share_code": share_code,
            }

            candidate_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO candidates
                   (id, enterprise_id, user_id, name, email, profile_data, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'new')""",
                (
                    candidate_id,
                    enterprise_id,
                    seeker_id,
                    display_name,
                    user.get("email"),
                    json.dumps(profile_data, ensure_ascii=False),
                ),
            )

            row = conn.execute(
                "SELECT * FROM candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()

        result = _candidate_response(dict(row))
        result["imported"] = True
        log_product_event(
            db,
            EVENT_CANDIDATE_IMPORTED,
            user_id=g.user_id,
            share_code=share_code,
            platform=platform_from_request(request),
            source="server",
            properties={"candidate_id": candidate_id, "seeker_id": seeker_id},
        )
        return jsonify(result), 201
    except Exception as e:
        return jsonify(error="import_failed", message=str(e)), 500


@enterprise_bp.route("/candidates/add", methods=["POST"])
@require_auth
@require_tier("supporter")
def add_candidate():
    """Add a candidate to the enterprise."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "")
    phone = data.get("phone", "")
    profile_data = data.get("profile_data")

    if not name:
        return jsonify(error="bad_request", message="candidate name required"), 400

    db = current_app._db

    try:
        with db.get_conn() as conn:
            # Find user's enterprise
            eu_row = conn.execute(
                "SELECT enterprise_id FROM enterprise_users WHERE user_id = ?",
                (g.user_id,)
            ).fetchone()

            if not eu_row:
                return jsonify(error="not_found", message="不属于任何企业"), 404

            enterprise_id = dict(eu_row)["enterprise_id"]

            blocked = _check_candidate_capacity(conn, enterprise_id, g.user_tier)
            if blocked:
                return blocked

            conn.execute(
                """INSERT INTO candidates (id, enterprise_id, name, email, phone, profile_data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), enterprise_id, name, email, phone,
                 json.dumps(profile_data) if profile_data else None)
            )

        return jsonify(name=name, email=email, status="new"), 201
    except Exception as e:
        return jsonify(error="add_failed", message=str(e)), 500


def _notify_sales_webhook(inquiry: dict):
    """MVP: POST inquiry to DingTalk/Feishu webhook if configured."""
    webhook_url = os.getenv("SALES_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.info("[sales] new inquiry %s (no webhook configured)", inquiry.get("id"))
        return

    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "text",
            "content": {
                "text": (
                    f"【企业版咨询】\n"
                    f"公司：{inquiry.get('company_name')}\n"
                    f"联系人：{inquiry.get('contact_name')}\n"
                    f"邮箱：{inquiry.get('contact_email')}\n"
                    f"电话：{inquiry.get('contact_phone') or '未填'}\n"
                    f"规模：{inquiry.get('scale') or '未填'}\n"
                    f"留言：{inquiry.get('message') or '无'}"
                ),
            },
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.warning("[sales] webhook notify failed: %s", e)


@enterprise_bp.route("/contact-sales", methods=["POST"])
@optional_auth
def contact_sales():
    """Submit an enterprise sales inquiry (auth optional)."""
    data = request.get_json() or {}
    company_name = (data.get("company_name") or "").strip()
    contact_name = (data.get("contact_name") or "").strip()
    contact_email = (data.get("contact_email") or "").strip()

    if not company_name or not contact_name or not contact_email:
        return jsonify(
            error="bad_request",
            message="company_name, contact_name, contact_email required",
        ), 400

    db = current_app._db
    user_id = getattr(g, "user_id", None)
    if user_id and str(user_id).startswith("guest-"):
        user_id = None

    try:
        inquiry = db.create_sales_inquiry({
            "user_id": user_id,
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": (data.get("contact_phone") or "").strip(),
            "scale": (data.get("scale") or "").strip(),
            "message": (data.get("message") or "").strip(),
        })
        _notify_sales_webhook(inquiry)
        return jsonify(
            ok=True,
            id=inquiry["id"],
            message="已收到您的咨询，我们会尽快联系您",
        ), 201
    except Exception as e:
        return jsonify(error="submit_failed", message=str(e)), 500
