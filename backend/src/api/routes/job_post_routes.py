"""
Job post routes — HR 职位发布与管理。
Ownership: szbenyx

Endpoints:
  POST   /v1/job-posts              — 发布职位
  GET    /v1/job-posts              — 我的职位列表
  PUT    /v1/job-posts/<id>         — 编辑职位
  DELETE /v1/job-posts/<id>         — 下架职位
  GET    /v1/job-posts/<id>/matches — 该职位的匹配候选人
"""
from __future__ import annotations

import json

from flask import Blueprint, request, jsonify, current_app, g

from src.thomas_core.auth.decorators import require_auth, require_tier
from src.utils.tier_limits import get_job_post_limit, is_at_limit

job_post_bp = Blueprint("job_posts", __name__)


def _db():
    return current_app._db


def _parse_requirements(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, ensure_ascii=False)


def _job_post_response(row: dict) -> dict:
    result = dict(row)
    req = result.get("requirements")
    if req and isinstance(req, str) and req.startswith("["):
        try:
            result["requirements"] = json.loads(req)
        except json.JSONDecodeError:
            pass
    return result


def _check_job_post_capacity():
    tier = g.user_tier
    limit = get_job_post_limit(tier)
    if limit == 0:
        return jsonify(
            error="forbidden",
            message="需要升级至支持者版才能发布职位",
            upgrade={"tier": "supporter"},
        ), 403
    if limit is not None:
        count = _db().count_active_job_posts(g.user_id)
        if is_at_limit(count, tier, resource="job_post"):
            return jsonify(
                error="quota_exceeded",
                message=f"职位发布已达上限（{limit}个），请升级套餐",
                limit=limit,
                current=count,
                upgrade={"tier": "pro" if tier == "supporter" else "enterprise"},
            ), 429
    return None


@job_post_bp.route("/job-posts", methods=["POST"])
@require_auth
@require_tier("supporter")
def create_job_post():
    """Publish a new job post (supporter: 3, pro: 20, enterprise: unlimited)."""
    blocked = _check_job_post_capacity()
    if blocked:
        return blocked

    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(error="bad_request", message="title required"), 400

    try:
        post = _db().create_job_post(g.user_id, {
            "title": title,
            "company": (data.get("company") or "").strip(),
            "description": (data.get("description") or "").strip(),
            "requirements": _parse_requirements(data.get("requirements")),
            "status": data.get("status", "active"),
        })
        return jsonify(_job_post_response(post)), 201
    except Exception as e:
        return jsonify(error="create_failed", message=str(e)), 500


@job_post_bp.route("/job-posts", methods=["GET"])
@require_auth
@require_tier("supporter")
def list_job_posts():
    """List job posts owned by the current user."""
    try:
        posts = _db().get_job_posts_by_user(g.user_id)
        limit = get_job_post_limit(g.user_tier)
        return jsonify(
            job_posts=[_job_post_response(p) for p in posts],
            limit=limit,
            count=len(posts),
        )
    except Exception as e:
        return jsonify(error="list_failed", message=str(e)), 500


@job_post_bp.route("/job-posts/<post_id>", methods=["PUT"])
@require_auth
@require_tier("supporter")
def update_job_post(post_id: str):
    """Update an existing job post."""
    data = request.get_json() or {}
    if "requirements" in data:
        data["requirements"] = _parse_requirements(data["requirements"])

    try:
        existing = _db().get_job_post(post_id, g.user_id)
        if not existing:
            return jsonify(error="not_found", message="职位不存在"), 404

        if data.get("status") == "active" and existing.get("status") != "active":
            blocked = _check_job_post_capacity()
            if blocked:
                return blocked

        updated = _db().update_job_post(post_id, g.user_id, data)
        return jsonify(_job_post_response(updated))
    except Exception as e:
        return jsonify(error="update_failed", message=str(e)), 500


@job_post_bp.route("/job-posts/<post_id>", methods=["DELETE"])
@require_auth
@require_tier("supporter")
def delete_job_post(post_id: str):
    """Remove a job post."""
    try:
        deleted = _db().delete_job_post(post_id, g.user_id)
        if not deleted:
            return jsonify(error="not_found", message="职位不存在"), 404
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error="delete_failed", message=str(e)), 500


def _score_candidate_match(candidate: dict, job_post: dict) -> float:
    """Simple keyword overlap scoring for MVP matching."""
    requirements = (job_post.get("requirements") or "").lower()
    if isinstance(requirements, list):
        requirements = " ".join(str(r) for r in requirements).lower()
    description = (job_post.get("description") or "").lower()
    keywords = set((requirements + " " + description).split())
    keywords = {k for k in keywords if len(k) > 2}
    if not keywords:
        return 0.5

    profile = candidate.get("profile_data") or {}
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except json.JSONDecodeError:
            profile = {}
    profile_text = json.dumps(profile, ensure_ascii=False).lower()
    hits = sum(1 for kw in keywords if kw in profile_text)
    return round(min(hits / max(len(keywords), 1), 1.0), 2)


@job_post_bp.route("/job-posts/<post_id>/matches", methods=["GET"])
@require_auth
@require_tier("supporter")
def job_post_matches(post_id: str):
    """Return candidates matched to this job post."""
    db = _db()
    try:
        post = db.get_job_post(post_id, g.user_id)
        if not post:
            return jsonify(error="not_found", message="职位不存在"), 404

        with db.get_conn() as conn:
            eu = conn.execute(
                "SELECT enterprise_id FROM enterprise_users WHERE user_id = ?",
                (g.user_id,),
            ).fetchone()
            if not eu:
                return jsonify(error="not_found", message="请先创建或加入企业"), 404

            enterprise_id = dict(eu)["enterprise_id"]
            rows = conn.execute(
                "SELECT * FROM candidates WHERE enterprise_id = ? ORDER BY created_at DESC",
                (enterprise_id,),
            ).fetchall()

        matches = []
        for row in rows:
            cand = dict(row)
            cand["profile_data"] = _parse_profile_data(cand.get("profile_data"))
            score = _score_candidate_match(cand, post)
            matches.append({
                "candidate": cand,
                "match_score": score,
            })

        matches.sort(key=lambda m: m["match_score"], reverse=True)
        return jsonify(
            job_post=_job_post_response(post),
            matches=matches,
            total=len(matches),
        )
    except Exception as e:
        return jsonify(error="match_failed", message=str(e)), 500


def _parse_profile_data(raw) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
