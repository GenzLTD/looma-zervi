"""Best-effort timeline writers — never raise into business callers."""
from __future__ import annotations

import logging
from typing import Any

from src.timeline.constants import (
    EVENT_KIND_ALLOW_DUPLICATE,
    FORBIDDEN_PAYLOAD_KEYS,
    HYPOTHESIS_WEIGHT_CAPS,
)

logger = logging.getLogger("looma.timeline")


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in FORBIDDEN_PAYLOAD_KEYS:
            logger.warning("Timeline PII blocked: key=%s", key)
            continue
        if isinstance(value, str) and len(value) > 2000:
            value = value[:2000]
        safe[key] = value
    return safe


def hypothesis_weight_cap(active_months: float) -> float:
    for months, cap in HYPOTHESIS_WEIGHT_CAPS:
        if active_months <= months:
            return cap
    return 0.1


def record_timeline_event(db, user_id: str, event_kind: str, source_system: str, **kwargs) -> dict | None:
    """Best-effort insert; returns row dict or None on failure."""
    try:
        payload = sanitize_payload(kwargs.pop("payload", None))
        allow_duplicate = kwargs.pop(
            "allow_duplicate",
            event_kind in EVENT_KIND_ALLOW_DUPLICATE,
        )
        return db.insert_timeline_event(
            user_id=user_id,
            event_kind=event_kind,
            source_system=source_system,
            payload=payload,
            allow_duplicate=allow_duplicate,
            **kwargs,
        )
    except Exception as e:
        logger.warning("record_timeline_event failed: %s %s", event_kind, e)
        return None


def record_quiz_hypothesis(
    db,
    user_id: str,
    personality_type: str,
    *,
    personality_detail: Any = None,
    source_ref: str | None = None,
) -> None:
    """Write quiz_completed + initial_hypothesis after profile-sync.

    Does not replace trust_memory or product_events — additive only.
    """
    ref = source_ref or f"profile_sync_{user_id}"
    detail_chars = 0
    if isinstance(personality_detail, str):
        detail_chars = len(personality_detail)
    elif personality_detail is not None:
        detail_chars = len(str(personality_detail))

    record_timeline_event(
        db,
        user_id,
        "quiz_completed",
        "quiz",
        source_ref=ref,
        title="完成职业画像初测",
        summary=(
            f"当前方向：{personality_type}。这是起始判断，会随经历调整。"
            if personality_type
            else "你完成了职业画像初测。"
        ),
        payload={
            "personality_type": personality_type,
            "detail_chars": detail_chars,
        },
        signal_quality="observed",
        confidence=0.9,
        weight_role="evidence",
        visibility="private",
    )
    record_timeline_event(
        db,
        user_id,
        "initial_hypothesis",
        "quiz",
        source_ref=ref,
        title="起始画像",
        summary=(
            f"当前方向：{personality_type}。这是起始画像，后续会根据实际经历持续调整。"
            if personality_type
            else "这是起始画像，后续会根据实际经历持续调整。"
        ),
        payload={
            "personality_type": personality_type,
            "personality_detail_ref": "game_profiles",
            "label": "initial_hypothesis",
            "decay_class": "bei_like",
        },
        signal_quality="hypothesis",
        confidence=0.4,
        weight_role="hypothesis",
        visibility="private",
    )


def serialize_timeline_row(row: dict) -> dict:
    """DB row → API shape."""
    import json

    payload = row.get("payload_json") or "{}"
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    consent = row.get("consent_scope") or "[]"
    if isinstance(consent, str):
        try:
            consent = json.loads(consent)
        except (json.JSONDecodeError, TypeError):
            consent = []
    return {
        "id": row.get("id"),
        "user_id": row.get("user_id"),
        "event_kind": row.get("event_kind"),
        "occurred_at": row.get("occurred_at"),
        "recorded_at": row.get("recorded_at"),
        "source_system": row.get("source_system"),
        "source_ref": row.get("source_ref") or "",
        "title": row.get("title") or "",
        "summary": row.get("summary") or "",
        "payload": payload,
        "signal_quality": row.get("signal_quality"),
        "confidence": row.get("confidence"),
        "weight_role": row.get("weight_role"),
        "visibility": row.get("visibility"),
        "consent_scope": consent,
        "status": row.get("status"),
        "superseded_by": row.get("superseded_by"),
    }


def compute_growth_stub(db, user_id: str) -> dict:
    """Minimal growth response — honest low confidence when sparse."""
    events = db.list_timeline_events(user_id, limit=100)
    active = [e for e in events if e.get("status") == "active"]
    n = len(active)
    kinds = {e.get("event_kind") for e in active}
    has_hypothesis = "initial_hypothesis" in kinds
    evidence_n = sum(1 for e in active if e.get("weight_role") == "evidence")

    if n < 3:
        confidence = "low"
        message = (
            "职业画像正在建立。先完成本周记录或添加一个项目，"
            "画像会随着实际经历逐渐准确。"
        )
    elif n < 8:
        confidence = "medium"
        message = (
            "你的职业画像正在完善中。初步判断已建立。"
            "继续记录实际行动和项目经历，可以进一步完善职业画像。"
        )
    else:
        confidence = "building"
        message = (
            "职业画像已有较完整的行为记录。"
            "持续记录每周行动和项目，画像会继续调整。"
        )

    # Rule-of-thumb dimensions (0-5) — not a real model yet
    action_density = min(5, evidence_n)
    exploration = min(5, len(kinds))
    expression = min(5, sum(1 for e in active if e.get("event_kind") in (
        "project_record", "interaction_log", "check_in",
    )))

    active_months = 0.0
    if active:
        # crude: count distinct YYYY-MM
        months = set()
        for e in active:
            ts = (e.get("occurred_at") or "")[:7]
            if len(ts) == 7:
                months.add(ts)
        active_months = float(len(months))

    return {
        "confidence": confidence,
        "message": message,
        "event_count": n,
        "hypothesis_present": has_hypothesis,
        "hypothesis_weight_cap": hypothesis_weight_cap(active_months or 0.5),
        "dimensions": [
            {
                "id": "action_density",
                "label": "行动密度",
                "level": action_density,
                "max": 5,
                "hint": "已留下的有效行为条数，满分 5",
            },
            {
                "id": "exploration",
                "label": "探索广度",
                "level": exploration,
                "max": 5,
                "hint": "尝试过的记录类型数，满分 5",
            },
            {
                "id": "expression",
                "label": "表达沉淀",
                "level": expression,
                "max": 5,
                "hint": "签到、项目、对话等主动记录，满分 5",
            },
        ],
        "version": "growth_stub_v0",
    }


def record_share_authorized(
    db,
    user_id: str,
    *,
    source_ref: str,
    channel: str,
    scope: list | None = None,
    reused: bool = False,
    occurred_at: str | None = None,
) -> dict | None:
    """Timeline node when user authorises sharing profile/attestations."""
    prefix = "sc_" if channel == "trust_verify" else "px_"
    return record_timeline_event(
        db,
        user_id,
        "share_authorized",
        "share",
        source_ref=source_ref,
        title="授权分享画像",
        summary="你向信任方开放了画像可见权限",
        payload={
            "share_code_prefix": prefix,
            "scope": scope or [],
            "channel": channel,
            "reused": bool(reused),
        },
        signal_quality="observed",
        confidence=0.85,
        weight_role="evidence",
        visibility="private",
        occurred_at=occurred_at,
    )


def record_match_scan(
    db,
    user_id: str,
    *,
    report_id: str,
    total_jobs: int = 0,
    max_score: float | None = None,
    avg_score: float | None = None,
    pipeline_version: str = "",
    has_resume_id: bool = False,
    occurred_at: str | None = None,
) -> dict | None:
    """Timeline node when a match report is saved (completed)."""
    return record_timeline_event(
        db,
        user_id,
        "match_scan",
        "match",
        source_ref=report_id,
        title="完成职位匹配扫描",
        summary=f"扫描 {total_jobs} 个岗位" if total_jobs else "保存匹配报告",
        payload={
            "total_jobs": total_jobs,
            "max_score": max_score,
            "avg_score": avg_score,
            "pipeline_version": pipeline_version or "",
            "has_resume_id": bool(has_resume_id),
        },
        signal_quality="observed",
        confidence=0.8,
        weight_role="evidence",
        visibility="private",
        occurred_at=occurred_at,
    )


def record_resume_ingest(
    db,
    user_id: str,
    *,
    source_ref: str,
    channel: str,
    skills_count: int = 0,
    years: str = "",
    degree: str = "",
    file_ext: str = "",
    raw_chars: int = 0,
    occurred_at: str | None = None,
) -> dict | None:
    """Timeline node after resume parse/upload (no full text)."""
    if user_id == "guest-anon":
        return None
    return record_timeline_event(
        db,
        user_id,
        "resume_ingest",
        "resume",
        source_ref=source_ref,
        title="沉淀简历摘要",
        summary="从简历提取结构化摘要（正文不入库时间线）",
        payload={
            "channel": channel,
            "skills_count": skills_count,
            "years": years or "",
            "degree": degree or "",
            "file_ext": file_ext or "",
            "raw_chars": raw_chars,
        },
        signal_quality="observed",
        confidence=0.7,
        weight_role="evidence",
        visibility="private",
        occurred_at=occurred_at,
    )


def record_learning_activity(
    db,
    user_id: str,
    *,
    source_ref: str,
    activity_type: str = "quiz",
    title: str = "完成学习活动",
    summary: str = "",
    score: int | float = 0,
    total: int = 0,
    correct_count: int = 0,
    result_type: str = "",
    occurred_at: str | None = None,
) -> dict | None:
    """Timeline node for quiz / learning sessions (HarmonyOS game quiz, etc.)."""
    if not user_id or user_id == "guest-anon":
        return None
    return record_timeline_event(
        db,
        user_id,
        "learning_activity",
        "quiz",
        source_ref=source_ref,
        title=title,
        summary=summary or f"{activity_type}: {correct_count}/{total}",
        payload={
            "activity_type": activity_type,
            "score": score,
            "total": total,
            "correct_count": correct_count,
            "result_type": result_type or "",
        },
        signal_quality="observed",
        confidence=0.85,
        weight_role="evidence",
        visibility="private",
        occurred_at=occurred_at,
    )


def record_mission_completed(
    db,
    user_id: str,
    *,
    mission_id: str,
    xp_reward: int = 0,
    occurred_at: str | None = None,
) -> dict | None:
    """Timeline node when a user completes a mission."""
    mission_labels: dict[str, str] = {
        "personality": "完成职业画像初测",
        "team": "组建舰队",
        "match": "完成星际匹配",
        "share": "发送星际信号",
    }
    return record_timeline_event(
        db,
        user_id,
        "mission_completed",
        "system",
        source_ref=mission_id,
        title=mission_labels.get(mission_id, f"完成任务: {mission_id}"),
        summary=f"获得 {xp_reward} 能量",
        payload={
            "mission_id": mission_id,
            "xp_reward": xp_reward,
        },
        signal_quality="observed",
        confidence=0.95,
        weight_role="evidence",
        visibility="private",
        occurred_at=occurred_at,
    )


def record_interaction_log(
    db,
    user_id: str,
    *,
    query: str,
    intent: str = "",
    intent_confidence: float = 0.0,
    response_time_ms: int = 0,
    ask_mode: str = "chat",
    occurred_at: str | None = None,
) -> dict | None:
    """Timeline node for each AI chat interaction."""
    if not user_id or user_id == "guest-anon":
        return None
    # Truncate query for safety and brevity
    summary = query[:120] + ("…" if len(query) > 120 else "")
    return record_timeline_event(
        db,
        user_id,
        "interaction_log",
        "ask",
        source_ref=f"ask_{intent}_{int(response_time_ms)}",
        title="对话交互",
        summary=summary,
        payload={
            "intent": intent or "",
            "intent_confidence": intent_confidence,
            "response_time_ms": response_time_ms,
            "ask_mode": ask_mode,
            "query_chars": len(query),
        },
        signal_quality="observed",
        confidence=0.75,
        weight_role="evidence",
        visibility="private",
        occurred_at=occurred_at,
    )


def backfill_user_timeline(db, user_id: str) -> list[str]:
    """Idempotent backfill: quiz / share / login / missions / match / resume."""
    written: list[str] = []
    profile = db.get_game_profile(user_id) or {}
    personality_type = (profile.get("personality_type") or "").strip()
    if personality_type:
        record_quiz_hypothesis(
            db,
            user_id,
            personality_type,
            personality_detail=profile.get("personality_detail"),
            source_ref=f"profile_sync_{user_id}",
        )
        written.extend(["quiz_completed", "initial_hypothesis"])

    # Account join (login/冷启动白名单) — one node per user
    try:
        with db.get_conn() as conn:
            user_row = conn.execute(
                "SELECT created_at FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user_row:
            record_timeline_event(
                db,
                user_id,
                "learning_activity",
                "system",
                source_ref=f"account_{user_id}",
                title="加入星际航线",
                summary="账号冷启动 · 航迹从此刻起算",
                payload={"activity_type": "account_joined"},
                signal_quality="observed",
                confidence=0.95,
                weight_role="evidence",
                visibility="private",
                occurred_at=user_row["created_at"],
            )
            written.append("learning_activity")
    except Exception as e:
        logger.warning("backfill account_joined failed: %s", e)

    # Mission completions → timeline thickness
    try:
        for m in db.get_user_missions(user_id):
            mid = m.get("mission_id") or ""
            if not mid:
                continue
            record_mission_completed(
                db,
                user_id,
                mission_id=mid,
                xp_reward=int(m.get("xp_reward") or 0),
                occurred_at=m.get("completed_at"),
            )
            written.append("mission_completed")
    except Exception as e:
        logger.warning("backfill missions failed: %s", e)

    # Trust share_codes
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, scope, created_at FROM share_codes
                   WHERE owner_id = ? AND status != 'revoked'""",
                (user_id,),
            ).fetchall()
        for r in rows:
            scope = r["scope"]
            if isinstance(scope, str):
                import json
                try:
                    scope = json.loads(scope)
                except (json.JSONDecodeError, TypeError):
                    scope = []
            record_share_authorized(
                db,
                user_id,
                source_ref=r["id"],
                channel="trust_verify",
                scope=scope if isinstance(scope, list) else [],
                occurred_at=r["created_at"],
            )
            written.append("share_authorized")
    except Exception as e:
        logger.warning("backfill share_codes failed: %s", e)

    # Referral invite codes (growth + profile_share)
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, tier_grant, created_at FROM invite_codes
                   WHERE created_by = ?""",
                (user_id,),
            ).fetchall()
        for r in rows:
            grant = r["tier_grant"] or "free"
            channel = "profile_share" if grant == "profile_share" else "referral_invite"
            record_share_authorized(
                db,
                user_id,
                source_ref=r["id"],
                channel=channel,
                scope=[channel],
                occurred_at=r["created_at"],
            )
            written.append("share_authorized")
    except Exception as e:
        logger.warning("backfill invite_codes failed: %s", e)

    # Completed match reports
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, metadata, resume_id, created_at FROM match_reports
                   WHERE user_id = ? AND status = 'completed'""",
                (user_id,),
            ).fetchall()
        import json
        for r in rows:
            meta = r["metadata"] or "{}"
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            record_match_scan(
                db,
                user_id,
                report_id=r["id"],
                total_jobs=int(meta.get("total_jobs") or 0),
                max_score=meta.get("max_score"),
                avg_score=meta.get("avg_score"),
                pipeline_version=str(meta.get("pipeline_version") or ""),
                has_resume_id=bool(r["resume_id"]),
                occurred_at=r["created_at"],
            )
            written.append("match_scan")
    except Exception as e:
        logger.warning("backfill match_reports failed: %s", e)

    # Resume trust memories as ingest proxies
    try:
        memories = db.get_trust_memories(user_id, session_type="resume", limit=20)
        for m in memories:
            content = m.get("memory_content") or "{}"
            if isinstance(content, str):
                import json
                try:
                    content = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    content = {}
            skills = content.get("skills_claimed") or []
            record_resume_ingest(
                db,
                user_id,
                source_ref=m.get("session_id") or m.get("id"),
                channel="trust_memory",
                skills_count=len(skills) if isinstance(skills, list) else 0,
                years=str(content.get("years") or ""),
                degree=str(content.get("education") or ""),
                occurred_at=m.get("created_at"),
            )
            written.append("resume_ingest")
    except Exception as e:
        logger.warning("backfill resume memories failed: %s", e)

    # unique preserve order
    seen = set()
    out = []
    for k in written:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


# Kinds safe to surface as L1 aggregate labels (no private payloads)
_L1_KIND_LABELS = {
    "initial_hypothesis": "起始画像",
    "quiz_completed": "职业画像初测",
    "project_record": "项目经历",
    "check_in": "本周记录",
    "share_authorized": "授权分享",
    "match_scan": "匹配扫描",
    "resume_ingest": "简历沉淀",
    "interaction_log": "对话沉淀",
    "mission_completed": "任务完成",
    "learning_activity": "学习行为",
}


def build_timeline_l1_summary(db, user_id: str) -> dict:
    """Public/HR-safe L1 thickness summary — aggregates only, no private payloads.

    Used by profile-view (share link) and enterprise candidate detail.
    """
    events = db.list_timeline_events(user_id, limit=100)
    active = [e for e in events if e.get("status") == "active"]
    n = len(active)
    kinds = [e.get("event_kind") for e in active]
    behavior_kinds = {
        "project_record",
        "check_in",
        "match_scan",
        "resume_ingest",
        "interaction_log",
        "mission_completed",
        "learning_activity",
        "fleet_co_presence",
    }
    evidence_behavior = [e for e in active if e.get("event_kind") in behavior_kinds]
    project_count = sum(1 for k in kinds if k == "project_record")
    check_in_count = sum(1 for k in kinds if k == "check_in")
    has_thickness = len(evidence_behavior) >= 1

    last_active_at = None
    if active:
        last_active_at = active[0].get("occurred_at") or active[0].get("recorded_at")

    recent_labels = []
    seen = set()
    for e in active[:5]:
        kind = e.get("event_kind") or ""
        label = _L1_KIND_LABELS.get(kind, kind)
        if label and label not in seen:
            seen.add(label)
            recent_labels.append(label)

    if n == 0:
        message = "尚无足够行为沉淀，画像厚度不足"
        confidence = "empty"
    elif not has_thickness:
        message = "目前主要是冷启动测评假设，行为沉淀仍不足"
        confidence = "thin"
    elif n < 5:
        message = "已有初步行为节点，画像仍在浮现中"
        confidence = "building"
    else:
        message = "行为时间线正在变厚"
        confidence = "building"

    return {
        "level": "l1",
        "event_count": n,
        "evidence_count": len(evidence_behavior),
        "project_count": project_count,
        "check_in_count": check_in_count,
        "has_thickness": has_thickness,
        "hypothesis_present": "initial_hypothesis" in kinds,
        "confidence": confidence,
        "message": message,
        "last_active_at": last_active_at,
        "recent_labels": recent_labels,
    }

