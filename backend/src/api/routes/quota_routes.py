"""
Quota routes blueprint.
Ownership: JOINT

Endpoints:
  GET /v1/quota      - Get current quota usage (alias)
  GET /v1/auth/quota - Get current quota usage (auth namespace)
"""
from flask import Blueprint, jsonify, g

from src.thomas_core.auth.decorators import require_auth
from src.thomas_core.quota import QUOTA_LIMITS, get_remaining, RESOURCE_ASK, RESOURCE_JOB_MATCH, RESOURCE_RESUME_PARSE, RESOURCE_RAG

quota_bp = Blueprint("quota", __name__)


@quota_bp.route("/quota", methods=["GET"])
@require_auth
def get_quota():
    """Get quota usage for the current user."""
    tier = g.get("user_tier", "free")
    limits = QUOTA_LIMITS.get(tier, QUOTA_LIMITS["guest"])

    records = []
    for resource, limit in limits.items():
        remaining = get_remaining(g.user_id, tier, resource)
        used = limit - remaining
        records.append({
            "resource": resource,
            "used": used,
            "daily_limit": limit,
        })

    return jsonify(tier=tier, records=records)
