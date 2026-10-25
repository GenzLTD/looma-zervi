"""
Act 1 State Machine — per-session step progression.
Ownership: Jason

Tracks each player's progress through the Act 1 narrative.
Supports both single-domain and cross-domain (职业域→诗域) paths.

Single-domain path (non-职业域):
  0=开场 1=信号 2=初遇 3=选择 4=后果 5=收敛 6=钩子 7=完成

Cross-domain path (职业域 only, GDD §9.2):
  0=开场 1=信号 2=初遇 3=选择 4=后果
  5=跨域触发 6=诗域初遇 7=诗域选择 8=诗域后果+回声
  9=收敛 10=钩子 11=完成

Ref: GDD §5.1 Act 1 Narrative Node Graph / §9.2 Vertical Slice
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("looma.act1")

# Step mapping: single-domain steps → cross-domain steps
# Non-career domains skip cross-domain steps (5-8)
CROSS_DOMAIN_START = 5   # step where cross-domain phase begins
CONVERGENCE_SHIFT = 4    # non-career domains get convergence shifted by this much
MAX_SINGLE_STEP = 7
MAX_CROSS_STEP = 11


@dataclass
class Act1SessionState:
    """Per-session Act 1 progression state."""
    session_id: str
    user_id: str = "guest"
    domain: str = ""                # selected domain (职业域 / 身份域 / ...)
    step: int = 0                   # 0-7 (single) or 0-11 (cross)
    chosen_option: int | None = None  # index of first choice (domain choice, 0-2)
    cross_chosen: int | None = None   # index of cross-domain choice (0-2)
    has_cross_domain: bool = False    # True if this session has cross-domain phase
    started_at: float = 0.0
    completed: bool = False

    def to_dict(self) -> dict:
        from src.agents.narrative_content import ACT1_STEPS, ACT1_STEPS_CROSS, DOMAIN_CONTENT

        # Determine which step labels to use
        is_cross = self.has_cross_domain
        step_labels = ACT1_STEPS_CROSS if is_cross else ACT1_STEPS

        step_info = step_labels[min(self.step, len(step_labels) - 1)]
        domain_info = None
        if self.domain and self.domain in DOMAIN_CONTENT:
            d = DOMAIN_CONTENT[self.domain]
            domain_info = {
                "name": self.domain,
                "icon": d["icon"],
                "color": d["color"],
                "emotion_arc": d["emotion_arc"],
            }

        total_steps = len(step_labels) - 1  # last step is "完成"

        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "domain": self.domain,
            "domain_info": domain_info,
            "step": self.step,
            "step_label": step_info["label"],
            "step_desc": step_info["desc"],
            "chosen_option": self.chosen_option,
            "cross_chosen": self.cross_chosen,
            "has_cross_domain": self.has_cross_domain,
            "completed": self.completed or self.step >= total_steps,
            "remaining_steps": max(0, total_steps - 1 - self.step),
        }

    def to_json(self) -> str:
        """Serialize for DB persistence."""
        return json.dumps({
            "session_id": self.session_id,
            "user_id": self.user_id,
            "domain": self.domain,
            "step": self.step,
            "chosen_option": self.chosen_option,
            "cross_chosen": self.cross_chosen,
            "has_cross_domain": self.has_cross_domain,
            "started_at": self.started_at,
            "completed": self.completed,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "Act1SessionState":
        """Restore from DB serialization."""
        data = json.loads(json_str)
        return cls(
            session_id=data["session_id"],
            user_id=data.get("user_id", "guest"),
            domain=data.get("domain", ""),
            step=data.get("step", 0),
            chosen_option=data.get("chosen_option"),
            cross_chosen=data.get("cross_chosen"),
            has_cross_domain=data.get("has_cross_domain", False),
            started_at=data.get("started_at", time.time()),
            completed=data.get("completed", False),
        )


# ============================================================================
# State Machine
# ============================================================================

class Act1StateMachine:
    """Manages per-session Act 1 step progression with cross-domain support."""

    def __init__(self, db=None):
        self._sessions: dict[str, Act1SessionState] = {}
        self._db = db  # DatabaseManager for persistence

    def _set_db(self, db):
        """Inject database manager (lazy binding)."""
        self._db = db

    def _persist(self, state: Act1SessionState):
        """Save state to DB if available."""
        if self._db is None:
            return
        try:
            self._db.save_act1_state(state.session_id, state.to_json())
        except Exception as e:
            logger.warning(f"Failed to persist Act1 state: {e}")

    def _load_from_db(self, session_id: str) -> Act1SessionState | None:
        """Try to load state from DB."""
        if self._db is None:
            return None
        try:
            json_str = self._db.get_act1_state(session_id)
            if json_str:
                return Act1SessionState.from_json(json_str)
        except Exception as e:
            logger.warning(f"Failed to load Act1 state from DB: {e}")
        return None

    def init_session(self, session_id: str, user_id: str = "guest") -> Act1SessionState:
        """Initialize a new Act 1 session at step 0. Tries DB restore first."""
        # Try restore from DB first
        restored = self._load_from_db(session_id)
        if restored:
            self._sessions[session_id] = restored
            logger.info(f"Act1 session restored from DB: {session_id}")
            return restored

        state = Act1SessionState(
            session_id=session_id,
            user_id=user_id,
            step=0,
            started_at=time.time(),
        )
        self._sessions[session_id] = state
        self._persist(state)
        logger.info(f"Act1 session initialized: {session_id} user={user_id}")
        return state

    def get_state(self, session_id: str) -> Act1SessionState | None:
        """Get current Act 1 state for a session. Falls back to DB."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        # Try DB restore
        restored = self._load_from_db(session_id)
        if restored:
            self._sessions[session_id] = restored
            return restored
        return None

    def select_domain(self, session_id: str, domain: str) -> Act1SessionState:
        """Record the player's domain selection. Sets has_cross_domain for 职业域."""
        state = self._get_or_init(session_id)
        state.domain = domain
        state.step = max(state.step, 0)
        state.has_cross_domain = (domain == "职业域")
        self._persist(state)
        logger.info(f"Act1 domain selected: {session_id} → {domain} "
                    f"(cross_domain={state.has_cross_domain})")
        return state

    def advance(self, session_id: str) -> dict:
        """Advance to the next step. Handles both single and cross-domain paths.

        Single-domain (step 0-7):
          0→1→2→3→4→5(收敛)→6(钩子)→7(完成)

        Cross-domain (step 0-11, 职业域 only):
          0→1→2→3→4→5(跨域触发)→6(诗域初遇)→7(诗域选择)
          →8(诗域后果+回声)→9(收敛)→10(钩子)→11(完成)
        """
        state = self._get_or_init(session_id)
        max_step = MAX_CROSS_STEP if state.has_cross_domain else MAX_SINGLE_STEP

        if state.step >= max_step:
            return {
                "step": state.step, "label": "已完成",
                "narrative": None, "choices": None, "choice_index": None,
                "completed": True,
            }

        # Guard: step 3→4 requires a choice
        if state.step == 3 and state.chosen_option is None:
            return {
                "step": 3, "label": "等待选择",
                "narrative": None, "choices": None, "choice_index": None,
                "error": "必须先做出选择",
            }

        # Guard: cross-domain choice step (7→8) requires cross_chosen
        if state.has_cross_domain and state.step == 7 and state.cross_chosen is None:
            return {
                "step": 7, "label": "等待选择",
                "narrative": None, "choices": None, "choice_index": None,
                "error": "必须先做出诗域选择",
            }

        prev_step = state.step
        state.step += 1

        # For non-cross-domain: skip from step 4 to step 5 (convergence shift is 0)
        # Nothing to skip — single-domain path is linear 0→1→2→3→4→5→6→7

        result = self._build_step_response(state, prev_step)
        result["prev_step"] = prev_step
        self._persist(state)
        return result

    def make_choice(self, session_id: str, choice_index: int) -> dict:
        """Record a choice. Handles both domain choice (step 3) and cross-domain choice (step 7)."""
        from src.agents.narrative_content import DOMAIN_CONTENT

        state = self._get_or_init(session_id)

        # Domain choice at step 3
        if state.step == 3:
            if choice_index < 0 or choice_index > 2:
                return {"step": state.step, "error": f"无效选项索引: {choice_index}"}

            state.chosen_option = choice_index
            domain_data = DOMAIN_CONTENT.get(state.domain, {})
            choice_data = domain_data.get("choices", [])[choice_index] if domain_data.get("choices") else {}

            result = {
                "step": state.step,
                "chosen_option": choice_index,
                "imprint_name": choice_data.get("imprint_name", ""),
                "imprint_axis": choice_data.get("imprint_axis", ""),
                "imprint_points": choice_data.get("imprint_points", 2),
            }
            self._persist(state)
            logger.info(f"Act1 domain choice: {session_id} domain={state.domain} "
                        f"option={choice_index} imprint={result['imprint_name']}")
            return result

        # Cross-domain choice at step 7 (poetry)
        if state.has_cross_domain and state.step == 7:
            if choice_index < 0 or choice_index > 2:
                return {"step": state.step, "error": f"无效选项索引: {choice_index}"}

            from src.agents.narrative_content import POETRY_CROSS_CONTENT

            state.cross_chosen = choice_index
            variant = POETRY_CROSS_CONTENT.get(state.chosen_option or 0, {})
            choice_data = variant.get("choices", [])[choice_index] if variant.get("choices") else {}

            result = {
                "step": state.step,
                "chosen_option": choice_index,
                "imprint_name": choice_data.get("imprint_name", ""),
                "imprint_axis": choice_data.get("imprint_axis", ""),
                "imprint_points": choice_data.get("imprint_points", 2),
                "is_cross_choice": True,
            }
            self._persist(state)
            logger.info(f"Act1 cross choice: {session_id} poetry option={choice_index} "
                        f"imprint={result['imprint_name']}")
            return result

        return {"step": state.step, "error": "当前不在选择节点"}

    def _build_step_response(self, state: Act1SessionState, prev_step: int) -> dict:
        """Build the narrative response for the current step."""
        from src.agents.narrative_content import (
            NAVIGATOR_LINES, DOMAIN_CONTENT, ACT1_STEPS, ACT1_STEPS_CROSS,
            CROSS_DOMAIN_TRIGGER, POETRY_CROSS_CONTENT, CROSS_ECHO_NARRATIVE,
        )

        is_cross = state.has_cross_domain
        step_labels = ACT1_STEPS_CROSS if is_cross else ACT1_STEPS
        step_info = step_labels[min(state.step, len(step_labels) - 1)]

        resp: dict = {
            "step": state.step,
            "label": step_info["label"],
            "desc": step_info["desc"],
            "domain": state.domain,
            "narrative": None,
            "navigator_line": None,
            "navigator_confidence": None,
            "choices": None,
            "choice_index": state.chosen_option,
            "has_cross_domain": is_cross,
            "completed": False,
        }

        domain_data = DOMAIN_CONTENT.get(state.domain, {}) if state.domain else {}
        career_choice = state.chosen_option or 0

        # ── Step-specific responses ──

        if state.step == 1:
            # Greeting carries the visible 0.3 uncertainty. The signal line stays in the narrative.
            greet = NAVIGATOR_LINES["greeting"]
            signal = NAVIGATOR_LINES["signal_flash"]
            resp["navigator_line"] = greet["line"]
            resp["navigator_confidence"] = greet["confidence"]
            resp["narrative"] = (
                f"{signal['line']}\n\n"
                f"Navigator 的声音在你周围回荡。\n\n"
                f"六域同时亮起。你选择了 {domain_data.get('icon', '')} {state.domain}。"
            )

        elif state.step == 2:
            # First encounter (domain-specific)
            resp["narrative"] = domain_data.get("encounter", "")
            resp["domain_emotion"] = domain_data.get("emotion_arc", "")

        elif state.step == 3:
            # Choice presented (domain-specific)
            choices = domain_data.get("choices", [])
            resp["narrative"] = "域内第二拍：第一个选择"
            resp["choices"] = [
                {"index": i, "label": c["label"]}
                for i, c in enumerate(choices)
            ]

        elif state.step == 4:
            # Consequence (domain)
            if state.chosen_option is not None:
                consequence = domain_data.get("choices", [])[state.chosen_option].get("consequence", "")
                imprint = domain_data.get("choices", [])[state.chosen_option].get("imprint_name", "")
                resp["narrative"] = consequence
                resp["imprint_name"] = imprint

        # ── Cross-domain steps (only for 职业域) ──
        elif is_cross and state.step == 5:
            # Cross-domain trigger: poetry domain lights up
            resp["navigator_line"] = CROSS_DOMAIN_TRIGGER["navigator_line"]
            resp["navigator_confidence"] = CROSS_DOMAIN_TRIGGER["confidence"]
            resp["narrative"] = CROSS_DOMAIN_TRIGGER["narrative"]
            resp["cross_domain_offer"] = True
            resp["cross_target"] = "诗域"

        elif is_cross and state.step == 6:
            # Poetry encounter (varies by career choice)
            variant = POETRY_CROSS_CONTENT.get(career_choice, POETRY_CROSS_CONTENT[0])
            resp["narrative"] = variant["encounter"]
            resp["domain_emotion"] = "共鸣→回声"
            resp["cross_variant"] = career_choice

        elif is_cross and state.step == 7:
            # Poetry choice
            variant = POETRY_CROSS_CONTENT.get(career_choice, POETRY_CROSS_CONTENT[0])
            resp["narrative"] = "选择你的诗句——它会在别处留下痕迹"
            resp["choices"] = [
                {"index": i, "label": c["label"]}
                for i, c in enumerate(variant["choices"])
            ]

        elif is_cross and state.step == 8:
            # Poetry consequence + cross-echo
            if state.cross_chosen is not None:
                variant = POETRY_CROSS_CONTENT.get(career_choice, POETRY_CROSS_CONTENT[0])
                poetry_consequence = variant.get("choices", [])[state.cross_chosen].get("consequence", "")
                imprint = variant.get("choices", [])[state.cross_chosen].get("imprint_name", "")
                resp["narrative"] = (
                    poetry_consequence + "\n\n"
                    + "—" * 20 + "\n\n"
                    + "⚡ 跨域回声触发\n\n"
                    + "你的诗句出现在了职业域的 JD 上。\n"
                    + "两个域——工作与诗歌——在这个瞬间被连在了一起。"
                )
                resp["imprint_name"] = imprint
                resp["echo_triggered"] = True

        # ── Convergence (step 5 single-domain, step 9 cross-domain) ──
        elif (not is_cross and state.step == 5) or (is_cross and state.step == 9):
            line = NAVIGATOR_LINES["convergence_glitch"]
            resp["navigator_line"] = line["line"]
            resp["navigator_confidence"] = line["confidence"]
            base_narrative = (
                "Navigator 突然停顿了。\n"
                "它的形态闪烁了一下——像是老式电视机的雪花。"
            )
            if is_cross:
                resp["narrative"] = base_narrative + "\n\n" + CROSS_ECHO_NARRATIVE
            else:
                resp["narrative"] = base_narrative
            if domain_data.get("convergence"):
                resp["convergence_texture"] = domain_data["convergence"]

        # ── Hook (step 6 single-domain, step 10 cross-domain) ──
        elif (not is_cross and state.step == 6) or (is_cross and state.step == 10):
            line = NAVIGATOR_LINES["recovery"]
            resp["navigator_line"] = line["line"]
            resp["navigator_confidence"] = line["confidence"]
            resp["narrative"] = (
                "Navigator 恢复正常了。\n"
                "它似乎不知道刚才发生了什么。\n\n"
                "但你已经在意了。\n"
                "T空间在等你。但不是为了工作。"
            )
            resp["end_hook"] = NAVIGATOR_LINES["act1_end"]["line"]

        # ── Complete ──
        elif state.step >= (MAX_CROSS_STEP if is_cross else MAX_SINGLE_STEP):
            resp["completed"] = True

        return resp

    def _get_or_init(self, session_id: str) -> Act1SessionState:
        """Get existing state or initialize a new one."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        return self.init_session(session_id)

    def reset(self, session_id: str):
        """Reset a session to step 0 (keep domain)."""
        if session_id in self._sessions:
            old = self._sessions[session_id]
            self._sessions[session_id] = Act1SessionState(
                session_id=session_id,
                user_id=old.user_id,
                domain=old.domain,
                has_cross_domain=old.has_cross_domain,
            )
            self._persist(self._sessions[session_id])
            logger.info(f"Act1 session reset: {session_id}")

    def hard_reset(self, session_id: str):
        """Full reset — clear domain and choice."""
        if session_id in self._sessions:
            old = self._sessions[session_id]
            self._sessions[session_id] = Act1SessionState(
                session_id=session_id,
                user_id=old.user_id,
                started_at=time.time(),
            )
            self._persist(self._sessions[session_id])
            logger.info(f"Act1 session hard reset: {session_id}")

    def end_session(self, session_id: str):
        """Clean up session from memory and mark as completed in DB."""
        if session_id in self._sessions:
            state = self._sessions[session_id]
            state.completed = True
            self._persist(state)
        self._sessions.pop(session_id, None)


# ============================================================================
# Singleton
# ============================================================================

_act1: Act1StateMachine | None = None


def get_act1(db=None) -> Act1StateMachine:
    """Get or create the singleton Act1StateMachine.
    If db is provided, inject it for persistence.
    """
    global _act1
    if _act1 is None:
        _act1 = Act1StateMachine(db=db)
    elif db is not None and _act1._db is None:
        _act1._set_db(db)
    return _act1


def reset_act1():
    """Reset state machine (for testing)."""
    global _act1
    _act1 = None
