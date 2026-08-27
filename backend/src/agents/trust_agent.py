"""
Trust Agent v0 — pure rule engine (no LLM).
Triggered on game completion callbacks to generate attestation claim cards.

Design: TRUST_PROFILE_DESIGN.md §5
Status: v0 MVP (2026-07-18)
"""
from __future__ import annotations
import json
import logging

logger = logging.getLogger("looma.trust_agent")

# ── Claim statement templates (v0: fixed templates, v1: LLM-generated) ──

_CLAIM_TEMPLATES = {
    "identity": "在压力下倾向战略型决策",
    "identity_resume": "已沉淀可核验的职业经历与技能主张",
    "identity_match": "已完成面向真实职位的匹配扫描",
    "collaboration": "能与不同风格的人完成协作任务",
    "communication": "能清晰表达复杂方案",
    "influence": "能带动他人参与和行动",
}

# ── Consistency helper ──


def _calc_quiz_consistency(quiz_memories: list[dict]) -> float:
    """Calculate personality consistency from quiz memory snapshots.
    Returns 0.0–1.0 where higher = more consistent answers.
    MVP: count unique personality_type values and derive a ratio.
    """
    if not quiz_memories:
        return 0.0
    types_seen = set()
    total = len(quiz_memories)
    for m in quiz_memories:
        try:
            content = json.loads(m["memory_content"]) if isinstance(m["memory_content"], str) else m["memory_content"]
            ptype = content.get("personality_type") or content.get("result_type")
            if ptype:
                types_seen.add(ptype)
        except (json.JSONDecodeError, TypeError, KeyError):
            total -= 1  # skip unparseable
    if total <= 0:
        return 0.0
    # Fewer distinct types across sessions = higher consistency
    return max(0.0, 1.0 - (len(types_seen) - 1) / total)


def _count_consensus(fleet_memories: list[dict]) -> int:
    """Count how many fleet memories have consensus_confirmed=True."""
    count = 0
    for m in fleet_memories:
        try:
            content = json.loads(m["memory_content"]) if isinstance(m["memory_content"], str) else m["memory_content"]
            if content.get("consensus_confirmed"):
                count += 1
        except (json.JSONDecodeError, TypeError):
            pass
    return count


# ── Main entry point ──


def generate_attestations(user_id: str, db) -> list[dict]:
    """Run Trust Agent v0 rules and upsert attestation cards.
    Called from game completion callbacks.
    Returns list of generated/updated attestation dicts.
    """
    memories = db.get_trust_memories(user_id, limit=200)
    results = []

    # ── 1. Identity (quiz preferred; else resume / match bridges) ──
    quiz_memories = [m for m in memories if m["session_type"] == "quiz"]
    resume_memories = [m for m in memories if m["session_type"] == "resume"]
    match_memories = [m for m in memories if m["session_type"] == "match"]

    if quiz_memories:
        consistency = _calc_quiz_consistency(quiz_memories)
        if consistency > 0.85:
            status = "verified"
            confidence = consistency
        elif consistency > 0.60:
            status = "weak"
            confidence = consistency
        else:
            status = "unverified"
            confidence = max(0.0, consistency)

        attestation = db.upsert_trust_attestation(
            candidate_id=user_id,
            claim_type="identity",
            claim_statement=_CLAIM_TEMPLATES["identity"],
            evidence_type="quiz",
            verification_status=status,
            evidence_refs=[m["id"] for m in quiz_memories],
            confidence_score=round(confidence, 2),
        )
        results.append(attestation)
        logger.info(
            "trust_agent: identity attestation for %s → %s (consistency=%.2f)",
            user_id, status, consistency,
        )
    elif resume_memories or match_memories:
        # T-space resume/match write memories but Agent v0 previously ignored them.
        # Self-claim alone never becomes "verified".
        refs = [m["id"] for m in resume_memories] + [m["id"] for m in match_memories]
        if resume_memories and match_memories:
            status, confidence = "weak", 0.45
            statement = _CLAIM_TEMPLATES["identity_resume"]
            evidence_type = "resume"
        elif resume_memories:
            status, confidence = "weak", 0.35
            statement = _CLAIM_TEMPLATES["identity_resume"]
            evidence_type = "resume"
        else:
            status, confidence = "unverified", 0.25
            statement = _CLAIM_TEMPLATES["identity_match"]
            evidence_type = "match_scan"

        attestation = db.upsert_trust_attestation(
            candidate_id=user_id,
            claim_type="identity",
            claim_statement=statement,
            evidence_type=evidence_type,
            verification_status=status,
            evidence_refs=refs,
            confidence_score=confidence,
        )
        results.append(attestation)
        logger.info(
            "trust_agent: identity (bridge) for %s → %s (resume=%d match=%d)",
            user_id, status, len(resume_memories), len(match_memories),
        )

    # ── 2. Collaboration (fleet + match consensus) ──
    fleet_memories = [m for m in memories if m["session_type"] == "fleet"]
    match_consensus_memories = [
        m for m in memories
        if m["session_type"] == "match" and _count_consensus([m]) > 0
    ]
    collab_memories = fleet_memories + match_consensus_memories
    if collab_memories:
        consensus_count = _count_consensus(collab_memories)
        if (len(fleet_memories) >= 3 and consensus_count >= 2) or consensus_count >= 1:
            status = "verified" if consensus_count >= 1 else "weak"
            confidence = 0.9 if consensus_count >= 1 else 0.5
        elif len(collab_memories) >= 1:
            status = "weak"
            confidence = 0.5
        else:
            status = "unverified"
            confidence = 0.0

        # 有双向 match consensus 时直接 verified
        if consensus_count >= 1:
            status, confidence = "verified", 0.9

        attestation = db.upsert_trust_attestation(
            candidate_id=user_id,
            claim_type="collaboration",
            claim_statement=_CLAIM_TEMPLATES["collaboration"],
            evidence_type="fleet_consensus" if fleet_memories else "match_consensus",
            verification_status=status,
            evidence_refs=[m["id"] for m in collab_memories],
            confidence_score=confidence,
        )
        results.append(attestation)
        logger.info(
            "trust_agent: collaboration attestation for %s → %s (fleets=%d, match_consensus=%d)",
            user_id, status, len(fleet_memories), len(match_consensus_memories),
        )

    # ── 3. Communication (ask) ──
    ask_memories = [m for m in memories if m["session_type"] == "ask"]
    if ask_memories:
        if len(ask_memories) >= 3:
            status = "verified"
            confidence = 0.85
        elif len(ask_memories) >= 1:
            status = "weak"
            confidence = 0.4
        else:
            status = "unverified"
            confidence = 0.0

        attestation = db.upsert_trust_attestation(
            candidate_id=user_id,
            claim_type="communication",
            claim_statement=_CLAIM_TEMPLATES["communication"],
            evidence_type="dialogue_analysis",
            verification_status=status,
            evidence_refs=[m["id"] for m in ask_memories],
            confidence_score=confidence,
        )
        results.append(attestation)
        logger.info("trust_agent: communication attestation for %s → %s (ask_sessions=%d)", user_id, status, len(ask_memories))

    # ── 4. Influence (share) ──
    share_memories = [m for m in memories if m["session_type"] == "share"]
    if share_memories:
        if len(share_memories) >= 3:
            status = "verified"
            confidence = 0.8
        elif len(share_memories) >= 1:
            status = "weak"
            confidence = 0.3
        else:
            status = "unverified"
            confidence = 0.0

        attestation = db.upsert_trust_attestation(
            candidate_id=user_id,
            claim_type="influence",
            claim_statement=_CLAIM_TEMPLATES["influence"],
            evidence_type="share_signal",
            verification_status=status,
            evidence_refs=[m["id"] for m in share_memories],
            confidence_score=confidence,
        )
        results.append(attestation)
        logger.info("trust_agent: influence attestation for %s → %s (share_events=%d)", user_id, status, len(share_memories))

    return results