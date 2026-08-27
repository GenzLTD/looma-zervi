"""
Referral routes blueprint.
Ownership: JOINT (dual review required)

Endpoints:
  POST /v1/referral/create          - Create a new invite code
  POST /v1/referral/use             - Consume an invite code
  GET  /v1/referral/my-codes        - List user's created invite codes
  GET  /v1/referral/profile-view/<code> - Public: view personality profile by share code
"""
from __future__ import annotations

import json
import uuid
from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth
from src.api.auth.jwt_handler import sign_token_for_user
from src.analytics.events import (
    log_product_event,
    platform_from_request,
    EVENT_SHARE_CODE_CREATED,
    EVENT_PROFILE_VIEW_PUBLIC,
    EVENT_PROFILE_VIEW_FAILED,
)

referral_bp = Blueprint("referral", __name__)

PROFILE_SHARE_GRANT = "profile_share"


def _parse_personality_detail(raw: str | None) -> dict | str | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


@referral_bp.route("/create", methods=["POST"])
@require_auth
def create_code():
    """Create a new invite code.

    Body:
      purpose: "referral" (default) | "profile_share"
      tier_grant: tier to grant when used (referral only; default "free")
    """
    data = request.get_json() or {}
    purpose = data.get("purpose", "referral")
    tier_grant = data.get("tier_grant", "free")

    if purpose == "profile_share":
        tier_grant = PROFILE_SHARE_GRANT

    db = current_app._db

    # Reuse existing profile share code for same user (view links are reusable)
    if purpose == "profile_share":
        try:
            with db.get_conn() as conn:
                existing = conn.execute(
                    """SELECT code FROM invite_codes
                       WHERE created_by = ? AND tier_grant = ?
                       ORDER BY created_at DESC LIMIT 1""",
                    (g.user_id, PROFILE_SHARE_GRANT),
                ).fetchone()
            if existing:
                code = dict(existing)["code"]
                log_product_event(
                    db,
                    EVENT_SHARE_CODE_CREATED,
                    user_id=g.user_id,
                    platform=platform_from_request(request),
                    share_code=code,
                    source="server",
                    properties={"reused": True},
                )
                try:
                    from src.timeline.events import record_share_authorized
                    with db.get_conn() as conn:
                        row = conn.execute(
                            """SELECT id FROM invite_codes
                               WHERE created_by = ? AND tier_grant = ? AND code = ?
                               ORDER BY created_at DESC LIMIT 1""",
                            (g.user_id, PROFILE_SHARE_GRANT, code),
                        ).fetchone()
                    if row:
                        record_share_authorized(
                            db,
                            g.user_id,
                            source_ref=dict(row)["id"],
                            channel="profile_share",
                            scope=["profile_share"],
                            reused=True,
                        )
                except Exception:
                    pass
                return jsonify(code=code, purpose=purpose, tier_grant=tier_grant), 200
        except Exception:
            pass

    code = str(uuid.uuid4())[:8].upper()
    invite_id = str(uuid.uuid4())

    try:
        with db.get_conn() as conn:
            conn.execute(
                """INSERT INTO invite_codes (id, code, created_by, tier_grant)
                   VALUES (?, ?, ?, ?)""",
                (invite_id, code, g.user_id, tier_grant),
            )
        if purpose == "profile_share":
            log_product_event(
                db,
                EVENT_SHARE_CODE_CREATED,
                user_id=g.user_id,
                platform=platform_from_request(request),
                share_code=code,
                source="server",
            )
            try:
                from src.timeline.events import record_share_authorized
                record_share_authorized(
                    db,
                    g.user_id,
                    source_ref=invite_id,
                    channel="profile_share",
                    scope=["profile_share"],
                )
            except Exception:
                pass
        return jsonify(code=code, purpose=purpose, tier_grant=tier_grant), 201
    except Exception as e:
        return jsonify(error="create_failed", message=str(e)), 500


@referral_bp.route("/use", methods=["POST"])
@require_auth
def use_code():
    """Consume an invite code (referral growth; not for profile_share codes)."""
    data = request.get_json() or {}
    code = data.get("code", "").strip().upper()

    if not code:
        return jsonify(error="bad_request", message="invite code required"), 400

    db = current_app._db

    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM invite_codes WHERE code = ? AND used_by IS NULL",
                (code,),
            ).fetchone()

            if not row:
                return jsonify(error="not_found", message="邀请码不存在或已被使用"), 404

            invite = dict(row)

            if invite.get("tier_grant") == PROFILE_SHARE_GRANT:
                return jsonify(
                    error="bad_request",
                    message="画像分享码不可用于注册核销，请使用普通邀请码",
                ), 400

            # Check expiry (compare as datetime strings in SQLite format)
            expires_at = invite.get("expires_at")
            if expires_at:
                now_row = conn.execute("SELECT datetime('now') AS now").fetchone()
                if expires_at < dict(now_row)["now"]:
                    return jsonify(error="expired", message="邀请码已过期"), 400

            conn.execute(
                """UPDATE invite_codes SET used_by = ?, used_at = datetime('now')
                   WHERE code = ?""",
                (g.user_id, code),
            )

            tier_grant = invite.get("tier_grant") or "free"
            tier_updated = False
            if tier_grant not in ("free", PROFILE_SHARE_GRANT):
                conn.execute(
                    "UPDATE users SET tier = ?, updated_at = datetime('now') WHERE id = ?",
                    (tier_grant, g.user_id),
                )
                tier_updated = True

        payload = {"consumed": True, "code": code, "tier_granted": invite.get("tier_grant", "free")}
        if tier_updated:
            access_token = sign_token_for_user(db, g.user_id)
            payload.update(
                access_token=access_token,
                token_type="bearer",
                expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
            )
        return jsonify(payload)
    except Exception as e:
        return jsonify(error="use_failed", message=str(e)), 500


@referral_bp.route("/profile-view/<code>", methods=["GET"])
def profile_view(code: str):
    """Public endpoint: view a job seeker's personality profile via share code."""
    code = code.strip().upper()
    if not code:
        return jsonify(error="bad_request", message="share code required"), 400

    db = current_app._db

    try:
        with db.get_conn() as conn:
            invite = conn.execute(
                "SELECT * FROM invite_codes WHERE code = ? AND tier_grant = ?",
                (code, PROFILE_SHARE_GRANT),
            ).fetchone()

            if not invite:
                log_product_event(
                    db,
                    EVENT_PROFILE_VIEW_FAILED,
                    share_code=code,
                    platform=platform_from_request(request),
                    source="server",
                    success=False,
                    properties={"reason": "invalid_code"},
                )
                return jsonify(error="not_found", message="分享码无效或已失效"), 404

            invite = dict(invite)
            creator_id = invite["created_by"]

            user_row = conn.execute(
                "SELECT id, name, email FROM users WHERE id = ?",
                (creator_id,),
            ).fetchone()
            profile_row = conn.execute(
                "SELECT * FROM game_profiles WHERE user_id = ?",
                (creator_id,),
            ).fetchone()

        if not profile_row:
            log_product_event(
                db,
                EVENT_PROFILE_VIEW_FAILED,
                share_code=code,
                platform=platform_from_request(request),
                source="server",
                success=False,
                properties={"reason": "no_profile"},
            )
            return jsonify(error="not_found", message="该用户尚未完成人格测试"), 404

        profile = dict(profile_row)
        user = dict(user_row) if user_row else {}
        detail = _parse_personality_detail(profile.get("personality_detail"))

        display_name = user.get("name") or user.get("email") or "求职者"
        if display_name and "@" in display_name:
            display_name = display_name.split("@")[0]

        log_product_event(
            db,
            EVENT_PROFILE_VIEW_PUBLIC,
            user_id=creator_id,
            share_code=code,
            platform=platform_from_request(request),
            source="server",
            properties={"personality_type": profile.get("personality_type")},
        )

        timeline_l1 = {}
        try:
            from src.timeline.events import build_timeline_l1_summary
            timeline_l1 = build_timeline_l1_summary(db, creator_id)
        except Exception:
            timeline_l1 = {
                "level": "l1",
                "event_count": 0,
                "has_thickness": False,
                "confidence": "empty",
                "message": "尚无足够行为沉淀，画像厚度不足",
                "recent_labels": [],
            }

        return jsonify(
            share_code=code,
            user_id=creator_id,
            user_display=display_name,
            personality_type=profile.get("personality_type"),
            personality_detail=detail,
            xp=profile.get("xp", 0),
            level=profile.get("level", 1),
            timeline_l1=timeline_l1,
        )
    except Exception as e:
        return jsonify(error="view_failed", message=str(e)), 500


@referral_bp.route("/my-codes", methods=["GET"])
@require_auth
def my_codes():
    """List invite codes created by the current user."""
    db = current_app._db

    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT code, tier_grant, used_by, used_at, created_at
                   FROM invite_codes WHERE created_by = ?
                   ORDER BY created_at DESC""",
                (g.user_id,),
            ).fetchall()
        codes = []
        for r in rows:
            row = dict(r)
            purpose = "profile_share" if row.get("tier_grant") == PROFILE_SHARE_GRANT else "referral"
            row["purpose"] = purpose
            codes.append(row)
        return jsonify(codes=codes)
    except Exception as e:
        return jsonify(error="list_failed", message=str(e)), 500
