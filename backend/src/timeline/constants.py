"""Timeline enums and PII guards — keep in sync with contracts/timeline.v1.json."""
from __future__ import annotations

EVENT_KIND_PHASE1 = frozenset({
    "initial_hypothesis",
    "quiz_completed",
    "project_record",
    "check_in",
    "interaction_log",
    "share_authorized",
    "match_scan",
    "resume_ingest",
    "mission_completed",
    "learning_activity",
})

EVENT_KIND_MANUAL = frozenset({
    "project_record",
    "check_in",
    "career_decision",
})

# kinds that may appear more than once for same source_ref
EVENT_KIND_ALLOW_DUPLICATE = frozenset({
    "check_in",
    "interaction_log",
    "match_scan",
})

SOURCE_SYSTEMS = frozenset({
    "quiz",
    "trust_memory",
    "match",
    "share",
    "resume",
    "ask",
    "fleet",
    "manual",
    "interview",
    "external",
    "system",
})

SIGNAL_QUALITIES = frozenset({
    "self_report",
    "observed",
    "external",
    "hypothesis",
})

WEIGHT_ROLES = frozenset({
    "hypothesis",
    "evidence",
    "calibration",
})

VISIBILITIES = frozenset({
    "private",
    "l1",
    "l2",
    "l3",
})

FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "email", "user_email", "phone", "mobile", "user_phone", "name", "user_name",
    "real_name", "contact_name", "id_card", "id_number", "passport", "ssn",
    "address", "home_address", "ip_address", "wechat_openid", "openid",
    "password", "token", "secret", "api_key", "resume_fulltext", "resume_text",
})

# Active-months → max weight for initial_hypothesis
HYPOTHESIS_WEIGHT_CAPS = (
    (1, 1.0),
    (3, 0.7),
    (6, 0.3),
    (10**9, 0.1),
)
