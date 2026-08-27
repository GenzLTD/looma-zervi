"""
Trust Protocol Layer — REST API routes.

Design: trust.v1.json §api_endpoints

Endpoints (candidate-facing, JWT required):
  GET  /v1/trust/attestations      — get user's attestation cards (with signatures)
  POST /v1/trust/refresh           — manually trigger Trust Agent re-evaluation
  POST /v1/trust/share-code        — generate temporary share_code
  DELETE /v1/trust/share-code/<id> — revoke a share_code
  GET  /v1/trust/share-codes       — list user's share_codes
  GET  /v1/trust/audit-log         — who viewed my attestations

Endpoints (public):
  GET  /v1/trust/.well-known/public-key — looma Ed25519 public key (PEM)
  POST /v1/trust/verify                — third-party verify attestations via share_code
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth
from src.agents.trust_agent import generate_attestations
from src.utils.crypto import sign_attestation, verify_attestation, get_public_key_pem

logger = logging.getLogger("looma.trust_routes")

_SHA_TZ = timezone(timedelta(hours=8))

trust_bp = Blueprint("trust", __name__)


def _get_db():
    return current_app._db


def _error(msg: str, code: str, status: int = 400) -> tuple:
    return jsonify(error=code, message=msg), status


def _build_attestation_response(att_row: dict) -> dict:
    """Convert a trust_attestations DB row into the public attestation JSON schema."""
    evidence_refs = att_row.get("evidence_refs", "[]")
    if isinstance(evidence_refs, str):
        try:
            evidence_refs = json.loads(evidence_refs)
        except (json.JSONDecodeError, TypeError):
            evidence_refs = []

    return {
        "attestation_id": att_row["id"],
        "candidate_id": att_row["candidate_id"],
        "claim_type": att_row["claim_type"],
        "claim_statement": att_row["claim_statement"],
        "evidence_type": att_row["evidence_type"],
        "verification_status": att_row["verification_status"],
        "evidence_refs": evidence_refs,
        "confidence_score": att_row.get("confidence_score", 0.0),
        "issued_at": att_row.get("created_at", ""),
        "expires_at": att_row.get("expires_at"),
        "signature": att_row.get("signature", ""),
    }


# =========================================================================
# Candidate-facing endpoints (JWT required)
# =========================================================================


@trust_bp.route("/attestations", methods=["GET"])
@require_auth
def get_attestations():
    """Get all trust attestation cards for the current user, with Ed25519 signatures."""
    db = _get_db()
    rows = db.get_trust_attestations(g.user_id)

    # Ensure each attestation has a signature; if not, sign it now and persist
    result = []
    for row in rows:
        if not row.get("signature"):
            body = _build_attestation_response(dict(row))
            sig = sign_attestation(body)
            # Default expiry: 90 days from created_at
            issued = row.get("created_at", "")
            try:
                issued_dt = datetime.fromisoformat(issued.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                issued_dt = datetime.now(_SHA_TZ)
            expires_dt = issued_dt + timedelta(days=90)
            expires_str = expires_dt.isoformat()
            db.update_attestation_signature(row["id"], sig, expires_str)
            body["signature"] = sig
            body["expires_at"] = expires_str
            result.append(body)
        else:
            result.append(_build_attestation_response(dict(row)))

    return jsonify(attestations=result, total=len(result))


@trust_bp.route("/refresh", methods=["POST"])
@require_auth
def refresh_attestations():
    """Manually trigger Trust Agent re-evaluation for the current user."""
    db = _get_db()
    try:
        results = generate_attestations(g.user_id, db)

        # Sign all newly generated/updated attestations
        signed_results = []
        for row in results:
            body = _build_attestation_response(dict(row))
            sig = sign_attestation(body)
            issued = row.get("created_at", "")
            try:
                issued_dt = datetime.fromisoformat(issued.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                issued_dt = datetime.now(_SHA_TZ)
            expires_dt = issued_dt + timedelta(days=90)
            expires_str = expires_dt.isoformat()
            db.update_attestation_signature(row["id"], sig, expires_str)
            body["signature"] = sig
            body["expires_at"] = expires_str
            signed_results.append(body)

        return jsonify(
            message="attestations refreshed",
            attestations=signed_results,
            total=len(signed_results),
        )
    except Exception as e:
        logger.exception("refresh_attestations failed for user %s", g.user_id)
        return _error(str(e), "server_error", 500)


@trust_bp.route("/share-code", methods=["POST"])
@require_auth
def create_share_code():
    """Generate a temporary share_code for third-party verification."""
    db = _get_db()
    body = request.get_json(silent=True) or {}

    scope = body.get("scope")
    if scope is None:
        scope = ["identity", "collaboration", "communication", "influence"]
    valid_types = {"identity", "collaboration", "communication", "influence"}
    scope = [s for s in scope if s in valid_types]
    if not scope:
        return _error("scope must contain at least one valid claim_type", "invalid_scope")

    max_access_count = min(max(int(body.get("max_access_count", 10)), 1), 100)
    expires_in_seconds = min(max(int(body.get("expires_in_seconds", 604800)), 60), 2592000)

    sc = db.create_share_code(
        owner_id=g.user_id,
        scope=scope,
        max_access_count=max_access_count,
        expires_in_seconds=expires_in_seconds,
    )

    try:
        from src.timeline.events import record_share_authorized
        record_share_authorized(
            db,
            g.user_id,
            source_ref=sc["id"],
            channel="trust_verify",
            scope=scope,
        )
    except Exception as e:
        logger.warning("timeline: share_authorized skipped for %s: %s", g.user_id, e)

    return jsonify(
        share_code=sc["code"],
        expires_at=sc["expires_at"],
        scope=sc["scope"],
        remaining_access_count=sc["max_access_count"] - sc["access_count"],
    ), 201


@trust_bp.route("/share-code/<code_id>", methods=["DELETE"])
@require_auth
def revoke_share_code(code_id: str):
    """Revoke a share_code (owner only)."""
    db = _get_db()
    ok = db.revoke_share_code(code_id, g.user_id)
    if not ok:
        return _error("share_code not found or not revokable", "share_code_not_found", 404)
    return jsonify(message="share_code revoked")


@trust_bp.route("/share-codes", methods=["GET"])
@require_auth
def list_share_codes():
    """List all share_codes for the current user."""
    db = _get_db()
    codes = db.list_share_codes(g.user_id)
    return jsonify(share_codes=codes, total=len(codes))


@trust_bp.route("/audit-log", methods=["GET"])
@require_auth
def get_audit_log():
    """Get the verification audit trail for the current user."""
    db = _get_db()
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    logs = db.get_verification_audit_log(g.user_id, limit=limit)
    return jsonify(audit_logs=logs, total=len(logs))


# =========================================================================
# Public endpoints (no JWT required)
# =========================================================================


@trust_bp.route("/.well-known/public-key", methods=["GET"])
def public_key():
    """Return looma's Ed25519 public key in PEM format for offline verification."""
    try:
        pem = get_public_key_pem()
        return jsonify(
            algorithm="Ed25519",
            public_key_pem=pem,
            usage="Use this key to verify looma_sig_v1 signatures on attestation JSON.",
        )
    except Exception as e:
        logger.exception("Failed to retrieve public key")
        return _error(str(e), "server_error", 500)


@trust_bp.route("/verify", methods=["POST"])
def verify_attestations():
    """Third-party verification endpoint. No JWT — authorised via share_code."""
    db = _get_db()
    body = request.get_json(silent=True) or {}
    share_code = body.get("share_code", "").strip()

    if not share_code:
        return _error("share_code is required", "missing_share_code")

    # Look up the share_code
    sc = db.get_share_code(share_code)
    if not sc:
        return _error("share_code not found", "share_code_not_found", 404)

    # Check status
    if sc["status"] == "revoked":
        verifier = _verifier_info()
        db.insert_verification_audit(share_code, sc["owner_id"], verifier, [], "revoked")
        return _error("share_code has been revoked", "share_code_revoked", 403)

    if sc["status"] == "expired":
        verifier = _verifier_info()
        db.insert_verification_audit(share_code, sc["owner_id"], verifier, [], "expired")
        return _error("share_code expired", "share_code_expired", 410)

    # Check time-based expiration
    now = datetime.now(_SHA_TZ).isoformat()
    if sc["expires_at"] < now:
        verifier = _verifier_info()
        db.insert_verification_audit(share_code, sc["owner_id"], verifier, [], "expired")
        return _error("share_code expired", "share_code_expired", 410)

    # Check access count
    if sc["access_count"] >= sc["max_access_count"]:
        verifier = _verifier_info()
        db.insert_verification_audit(share_code, sc["owner_id"], verifier, [], "exhausted")
        return _error("share_code exhausted (max access count reached)", "share_code_exhausted", 429)

    # Consume one access
    sc = db.consume_share_code(share_code)
    if not sc:
        verifier = _verifier_info()
        db.insert_verification_audit(share_code, sc or {} and sc.get("owner_id", ""), verifier, [], "exhausted")
        return _error("share_code could not be consumed", "share_code_exhausted", 429)

    # Retrieve attestations within scope
    scope = sc.get("scope", [])
    if isinstance(scope, str):
        try:
            scope = json.loads(scope)
        except (json.JSONDecodeError, TypeError):
            scope = []

    rows = db.get_trust_attestations_by_type(sc["owner_id"], scope)

    attestations = []
    for row in rows:
        att = _build_attestation_response(dict(row))
        # Sign if not already signed
        if not att.get("signature"):
            sig = sign_attestation(att)
            issued = row.get("created_at", "")
            try:
                issued_dt = datetime.fromisoformat(issued.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                issued_dt = datetime.now(_SHA_TZ)
            expires_dt = issued_dt + timedelta(days=90)
            expires_str = expires_dt.isoformat()
            db.update_attestation_signature(row["id"], sig, expires_str)
            att["signature"] = sig
            att["expires_at"] = expires_str
        attestations.append(att)

    # Log audit
    att_ids = [a["attestation_id"] for a in attestations]
    verifier = _verifier_info()
    db.insert_verification_audit(share_code, sc["owner_id"], verifier, att_ids, "success")

    # Get candidate name if available
    user = db.get_user_by_id(sc["owner_id"])
    candidate_alias = user.get("name", "Anonymous") if user else "Anonymous"

    return jsonify(
        attestations=attestations,
        candidate_alias=candidate_alias,
        verified_at=now,
        share_code_scope=scope,
    )


def _verifier_info() -> str:
    """Build a verifier_info string from the request context (no PII)."""
    ip = request.headers.get("X-Forwarded-For", request.headers.get("X-Real-IP", request.remote_addr or "unknown"))
    ua = request.headers.get("User-Agent", "unknown")
    return f"ip={ip} ua={ua}"