"""
Product analytics — server-side event logging for closed-loop funnel.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("looma.analytics")

# Closed-loop funnel event names (keep in sync with docs/内测埋点与闭环漏斗方案.md)
EVENT_QUIZ_COMPLETE = "quiz_complete"
EVENT_SHARE_CODE_CREATED = "share_code_created"
EVENT_PROFILE_VIEW_PUBLIC = "profile_view_public"
EVENT_PROFILE_VIEW_FAILED = "profile_view_failed"
EVENT_CANDIDATE_IMPORTED = "candidate_imported"
EVENT_CANDIDATE_IMPORT_DUPLICATE = "candidate_import_duplicate"
EVENT_TRIAL_STARTED = "trial_started"
EVENT_TRIAL_FAILED = "trial_failed"
EVENT_TIER_ACTIVATED = "tier_activated"

FORBIDDEN_PROPERTY_KEYS = frozenset({
    "email", "user_email", "phone", "mobile", "user_phone", "name", "user_name",
    "real_name", "contact_name", "id_card", "id_number", "passport", "ssn",
    "address", "home_address", "ip_address", "wechat_openid", "openid",
    "password", "token", "secret", "api_key",
})


def sanitize_event_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    """Strip known PII keys before persisting analytics properties."""
    if not properties:
        return {}
    safe: dict[str, Any] = {}
    for key, value in properties.items():
        if key.lower() in FORBIDDEN_PROPERTY_KEYS:
            logger.warning("Analytics PII blocked: key=%s", key)
            continue
        if isinstance(value, str) and len(value) > 500:
            value = value[:500]
        safe[key] = value
    return safe


def log_product_event(
    db,
    event_name: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    platform: str = "unknown",
    share_code: str | None = None,
    source: str = "server",
    success: bool = True,
    properties: dict[str, Any] | None = None,
) -> None:
    """Best-effort server-side analytics; never raises to callers."""
    try:
        db.log_product_event(
            event_name=event_name,
            user_id=user_id,
            session_id=session_id,
            platform=platform,
            share_code=share_code,
            source=source,
            success=success,
            properties=sanitize_event_properties(properties),
        )
    except Exception as e:
        logger.warning("log_product_event failed: %s %s", event_name, e)


def platform_from_request(request) -> str:
    """Infer platform from X-Platform header or User-Agent."""
    explicit = (request.headers.get("X-Platform") or "").strip().lower()
    if explicit in ("planetx_web", "planetx_mp", "tspace_web"):
        return explicit
    ua = (request.headers.get("User-Agent") or "").lower()
    if "miniprogram" in ua or "micromessenger" in ua:
        return "planetx_mp"
    if "mozilla" in ua or "chrome" in ua:
        return "tspace_web"
    return "unknown"
