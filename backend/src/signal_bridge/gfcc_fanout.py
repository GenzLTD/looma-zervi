"""GFCC chain-B fan-out — PlanetX → POST /v1/signal-ingest.

Maps PlanetX personality_beacon (user_email_hash / data / X-Signal-Signature)
onto frozen signal.envelope.v1 (user_id_hash / payload / X-Signature).

Chain A (DemoPPI) is unchanged. Missing URL/secret, unmapped personality
labels, or non-64-hex hashes → skip (never raise).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
import urllib.error
import urllib.request

logger = logging.getLogger("looma.gfcc_fanout")

HASH_RE = re.compile(r"^[a-f0-9]{64}$")

MBTI_TYPES = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
}

# PlanetX 六型中文标签 → GFCC 冻结 MBTI 16 型（适配层，不改测评产品面）
PLANETX_TO_MBTI = {
    "星云艺术家": "ENFP",
    "黑洞程序员": "INTJ",
    "超新星领航员": "ENTJ",
    "双星星系守护者": "ESFJ",
    "脉冲星修行者": "INFJ",
    "暗物质漫游者": "INFP",
}

BACKOFF_S = (1, 2, 4)


def map_personality_type(label: str) -> str | None:
    """Return an MBTI 16-type or None if the label cannot be mapped."""
    raw = (label or "").strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper in MBTI_TYPES:
        return upper
    return PLANETX_TO_MBTI.get(raw)


def _gfcc_traits(traits):
    """PlanetX traits may be string[] or {name,score}[]; GFCC requires the latter."""
    if not isinstance(traits, list) or not traits:
        return None
    out = []
    for item in traits:
        if isinstance(item, str) and item.strip():
            out.append({"name": item.strip(), "score": 1.0})
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            score = item.get("score", 1.0)
            if name and isinstance(score, (int, float)) and not isinstance(score, bool):
                out.append({"name": name, "score": float(score)})
        if len(out) >= 16:
            break
    return out or None


def to_gfcc_personality_beacon_envelope(
    email_hash,
    personality_type,
    traits,
    score,
    nonce,
    timestamp=None,
):
    """Build a frozen envelope or return ``{"skip": reason}``."""
    if not isinstance(email_hash, str) or not HASH_RE.fullmatch(email_hash):
        return {"skip": "user_id_hash_not_64_hex"}
    if not isinstance(nonce, str) or len(nonce) < 8:
        return {"skip": "nonce_too_short"}
    mbti = map_personality_type(personality_type)
    if not mbti:
        return {"skip": "personality_type_unmapped"}

    payload = {
        "personality_type": mbti,
        "source": "planetx",
    }
    mapped_traits = _gfcc_traits(traits)
    if mapped_traits is not None:
        payload["traits"] = mapped_traits
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        payload["assessment_score"] = float(score)
    if timestamp:
        payload["generated_at"] = timestamp

    envelope = {
        "signal_type": "personality_beacon",
        "user_id_hash": email_hash,
        "nonce": nonce,
        "payload": payload,
    }
    if timestamp:
        envelope["timestamp"] = timestamp
    return {"envelope": envelope}


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def post_gfcc_signal(envelope: dict, url: str, secret: str, max_retries: int = 3) -> dict:
    """HMAC-sign and POST. Returns ``{ok, status?, skipped?, reason?}``. Never raises."""
    if not secret:
        return {"ok": False, "skipped": True, "reason": "missing_gfcc_secret"}
    if not url:
        return {"ok": False, "skipped": True, "reason": "missing_gfcc_url"}

    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = _sign(body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
    }

    last_status = 0
    for attempt in range(max_retries + 1):
        if attempt > 0:
            time.sleep(BACKOFF_S[min(attempt - 1, len(BACKOFF_S) - 1)])
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                last_status = getattr(resp, "status", 200) or 200
                raw = resp.read()
                parsed = {}
                try:
                    parsed = json.loads(raw.decode("utf-8") or "{}")
                except (ValueError, TypeError):
                    parsed = {}
                duplicate = parsed.get("status") == "duplicate" or parsed.get("duplicate") is True
                return {"ok": True, "status": last_status, "duplicate": duplicate}
        except urllib.error.HTTPError as exc:
            last_status = exc.code
            if 400 <= exc.code < 500:
                logger.warning("gfcc-fanout permanent failure HTTP %s", exc.code)
                return {"ok": False, "status": exc.code}
        except Exception:
            last_status = 0

    logger.warning(
        "gfcc-fanout exhausted retries (lastStatus=%s) nonce=%s",
        last_status,
        envelope.get("nonce"),
    )
    return {"ok": False, "status": last_status}


def send_gfcc_personality_beacon(
    email_hash,
    personality_type,
    traits,
    score,
    nonce,
    timestamp=None,
    url="",
    secret="",
):
    mapped = to_gfcc_personality_beacon_envelope(
        email_hash, personality_type, traits, score, nonce, timestamp,
    )
    if "skip" in mapped:
        logger.info("gfcc-fanout skip personality_beacon: %s", mapped["skip"])
        return {"ok": False, "skipped": True, "reason": mapped["skip"]}
    return post_gfcc_signal(mapped["envelope"], url, secret)
