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


def _post_body(
    body: bytes,
    url: str,
    secret: str,
    max_retries: int = 3,
    nonce: str | None = None,
) -> dict:
    """HMAC-sign and POST an already-serialized body (byte-identical replay keeps
    X-Signature unchanged → remote nonce idempotency holds). Never raises.

    ``nonce`` 仅用于日志定位：信号丢失时它是值班唯一能拿到的线索（按 nonce 重发
    是 R2 的运维前提）。发件箱与重放路径都能拿到，调用方须传。
    """
    if not secret:
        return {"ok": False, "skipped": True, "reason": "missing_gfcc_secret"}
    if not url:
        return {"ok": False, "skipped": True, "reason": "missing_gfcc_url"}

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
                logger.warning(
                    "gfcc-fanout permanent failure HTTP %s nonce=%s", exc.code, nonce
                )
                return {"ok": False, "status": exc.code}
        except Exception:
            last_status = 0

    logger.warning(
        "gfcc-fanout exhausted retries (lastStatus=%s) nonce=%s",
        last_status,
        nonce,
    )
    return {"ok": False, "status": last_status}


def post_gfcc_signal(envelope: dict, url: str, secret: str, max_retries: int = 3) -> dict:
    """HMAC-sign and POST an envelope dict. Returns ``{ok, status?, duplicate?}``."""
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _post_body(
        body, url, secret, max_retries=max_retries, nonce=envelope.get("nonce")
    )


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


# ============================================================
# R2: 出站事务性发件箱 + 可重放 DLQ(PlanetX 发送侧)
# 契约语义: 信封 v1 不变 / nonce 幂等由对端保证 / 值班按 nonce 重发。
# 关键设计: outbox/DLQ 存的是「已序列化 body 原文」→ 重放逐字节一致 → 签名不变。
# ============================================================
def _envelope_to_body(envelope: dict) -> str:
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def deliver_outbox_pending(db, url: str, secret: str, max_items: int = 50, max_attempts: int = 3) -> dict:
    """扫 pending outbox 逐条投递。
    - ok(含 duplicate)→ mark_outbox_delivered
    - 4xx 永久失败 → 迁 DLQ(permanent_4xx)
    - 网络/5xx → attempts+1;超 max_attempts 迁 DLQ(network_error)
    返回 {delivered, dlq, pending_left}。Never raises。"""
    stats = {"delivered": 0, "dlq": 0, "pending_left": 0}
    for row in db.list_outbox_pending(limit=max_items):
        nonce = row["nonce"]
        res = _post_body(
            row["body"].encode("utf-8"), url, secret, max_retries=2, nonce=nonce
        )
        if res.get("ok"):
            db.mark_outbox_delivered(nonce)
            stats["delivered"] += 1
        elif res.get("status") and 400 <= res["status"] < 500:
            db.move_outbox_to_dlq(nonce, "permanent_4xx", f"HTTP {res['status']}")
            stats["dlq"] += 1
        else:
            err = res.get("reason") or f"status={res.get('status')}"
            db.bump_outbox_attempt(nonce, err)
            if row["attempts"] + 1 >= max_attempts:
                db.move_outbox_to_dlq(nonce, "network_error", err)
                stats["dlq"] += 1
    stats["pending_left"] = len(db.list_outbox_pending())
    return stats


def replay_dlq_entry(db, nonce: str, url: str, secret: str) -> dict:
    """值班按 nonce 从 DLQ 重发(原 body 逐字节 → 签名不变)。
    成功(含对端 duplicate)→ mark_dlq_replayed,审计留痕。Never raises。"""
    entry = db.get_dlq_by_nonce(nonce)
    if not entry:
        return {"ok": False, "reason": "not_in_dlq", "nonce": nonce}
    res = _post_body(
        entry["body"].encode("utf-8"), url, secret, max_retries=3, nonce=nonce
    )
    if res.get("ok"):
        db.mark_dlq_replayed(nonce)
        return {"ok": True, "nonce": nonce, "duplicate": bool(res.get("duplicate"))}
    return {
        "ok": False,
        "nonce": nonce,
        "status": res.get("status"),
        "reason": res.get("reason") or f"status={res.get('status')}",
    }


def send_gfcc_personality_beacon_outboxed(
    db,
    email_hash,
    personality_type,
    traits,
    score,
    nonce,
    timestamp=None,
    url="",
    secret="",
):
    """守契约出站: 先入 outbox(持久化)→ 立即尝试投递。
    - 入箱成功即返回, 失败留在 pending/DLQ 由重放兜底 → 发送方不丢信号。
    - skip(映射失败/hash 非法)→ 不落库(信封无效, 落库无意义)。
    返回 {ok, skipped?, outbox_nonce?, delivered?, dlq?, pending?}。Never raises。"""
    mapped = to_gfcc_personality_beacon_envelope(
        email_hash, personality_type, traits, score, nonce, timestamp,
    )
    if "skip" in mapped:
        logger.info("gfcc-fanout skip personality_beacon: %s", mapped["skip"])
        return {"ok": False, "skipped": True, "reason": mapped["skip"]}
    body = _envelope_to_body(mapped["envelope"])
    db.enqueue_signal_outbox("personality_beacon", nonce, body)
    deliver_outbox_pending(db, url, secret)
    row = db.get_outbox_by_nonce(nonce)
    if row and row["status"] == "delivered":
        return {"ok": True, "outbox_nonce": nonce, "delivered": True}
    if db.get_dlq_by_nonce(nonce):
        return {"ok": False, "outbox_nonce": nonce, "dlq": True}
    return {"ok": False, "outbox_nonce": nonce, "pending": True}
