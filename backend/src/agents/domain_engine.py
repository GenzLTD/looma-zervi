"""
Domain Interaction Engine — GDD §3 & §7 implementation.
Ownership: Jason

Core responsibilities:
  1. 6×6 Cross-Domain Interaction Matrix (✅/⚠️/🚫 enforcement)
  2. Value Imprint System (3 axes: survival/freedom/belonging)
  3. Cross-Domain Echo detection & triggering
  4. Emergent Strategy detection (5 playtest strategies)

Ref: PlanetX-T空间_游戏化预演设计_GDD.md §3.2/§3.3/§7.1-§7.3
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger("looma.domain_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOMAINS = ["职业域", "身份域", "诗域", "信任域", "自我域", "迷雾域"]
DOMAINS_EN = ["career", "identity", "poetry", "trust", "self", "unknown"]
DOMAIN_TO_EN = dict(zip(DOMAINS, DOMAINS_EN))
EN_TO_DOMAIN = dict(zip(DOMAINS_EN, DOMAINS))

# Value Axes (映射"钱多事少离家近")
AXES = ["survival", "freedom", "belonging"]  # 生存/自由/归属

# Domain → primary axis mapping
DOMAIN_AXIS = {
    "职业域": "survival",
    "身份域": "belonging",
    "诗域":   "freedom",
    "信任域": "survival",
    "自我域": "freedom",
    "迷雾域": "belonging",
}


class InteractionLevel(str, Enum):
    """6×6 matrix interaction classification."""
    INTENDED = "intended"       # ✅ 意图内交互
    ACCEPTABLE = "acceptable"   # ⚠️ 可接受交互
    FORBIDDEN = "forbidden"     # 🚫 禁止交互


class EchoType(str, Enum):
    CHARACTER = "character"     # 角色回声：NPC跨域出现
    ENVIRONMENT = "environment" # 环境回声：域环境细节在别域显现
    SYSTEM = "system"           # 系统回声：数值/状态影响可用选项
    NAVIGATOR = "navigator"     # Navigator回声：Navigator引用历史选择


class EmergentStrategy(str, Enum):
    POETRY_REFUGE = "poetry_refuge"         # 诗域避难所
    TRUST_FARMING = "trust_farming"          # 信任域刷分
    UNKNOWN_SPEEDRUN = "unknown_speedrun"    # 迷雾域速通
    MBTI_REJECTOR = "mbti_rejector"          # MBTI拒绝者
    CROSS_DOMAIN_HACKER = "cross_domain_hacker"  # 跨域黑客


# ===== §7.1: 6×6 Interaction Matrix =====
# source_domain × target_domain → (level, effect_description)
INTERACTION_MATRIX: dict[tuple[str, str], tuple[InteractionLevel, str]] = {
    # --- 职业域 → others ---
    ("职业域", "身份域"):  (InteractionLevel.INTENDED,    "简历影响匹配质量"),
    ("职业域", "诗域"):    (InteractionLevel.INTENDED,    "诗域NPC出现在工作场景"),
    ("职业域", "信任域"):  (InteractionLevel.INTENDED,    "信任分门控高端JD"),
    ("职业域", "自我域"):  (InteractionLevel.INTENDED,    "MBTI标签偏置推荐"),
    ("职业域", "迷雾域"):  (InteractionLevel.ACCEPTABLE,  "迷雾泄漏虚假JD数据"),
    # --- 身份域 → others ---
    ("身份域", "职业域"):  (InteractionLevel.INTENDED,    "职业选择重塑简历"),
    ("身份域", "诗域"):    (InteractionLevel.INTENDED,    "过去经历激发诗意"),
    ("身份域", "信任域"):  (InteractionLevel.INTENDED,    "简历空白降低信任"),
    ("身份域", "自我域"):  (InteractionLevel.INTENDED,    "MBTI挑战简历叙事"),
    ("身份域", "迷雾域"):  (InteractionLevel.ACCEPTABLE,  "迷雾使简历记忆碎片化"),
    # --- 诗域 → others ---
    ("诗域", "职业域"):    (InteractionLevel.INTENDED,    "工作压力触发诗意"),
    ("诗域", "身份域"):    (InteractionLevel.INTENDED,    "简历过去写成诗"),
    ("诗域", "信任域"):    (InteractionLevel.ACCEPTABLE,  "诗意表达有信任风险"),
    ("诗域", "自我域"):    (InteractionLevel.INTENDED,    "诗揭示真实自我"),
    ("诗域", "迷雾域"):    (InteractionLevel.INTENDED,    "迷雾域即诗（隐藏真相）"),
    # --- 信任域 → others ---
    ("信任域", "职业域"):  (InteractionLevel.INTENDED,    "工作表现影响信任"),
    ("信任域", "身份域"):  (InteractionLevel.INTENDED,    "简历空白影响信任"),
    ("信任域", "诗域"):    (InteractionLevel.ACCEPTABLE,  "信任审查压抑诗意"),
    ("信任域", "自我域"):  (InteractionLevel.INTENDED,    "MBTI类型影响信任算法"),
    ("信任域", "迷雾域"):  (InteractionLevel.FORBIDDEN,   "迷雾域无信任记录"),
    # --- 自我域 → others ---
    ("自我域", "职业域"):  (InteractionLevel.INTENDED,    "职业引用MBTI类型"),
    ("自我域", "身份域"):  (InteractionLevel.INTENDED,    "简历确认/反驳类型"),
    ("自我域", "诗域"):    (InteractionLevel.INTENDED,    "诗揭示真实类型"),
    ("自我域", "信任域"):  (InteractionLevel.INTENDED,    "信任分与类型相关"),
    ("自我域", "迷雾域"):  (InteractionLevel.INTENDED,    "迷雾域打破分类系统"),
    # --- 迷雾域 → others ---
    ("迷雾域", "职业域"):  (InteractionLevel.ACCEPTABLE,  "JD数据不可靠"),
    ("迷雾域", "身份域"):  (InteractionLevel.ACCEPTABLE,  "简历记忆碎片"),
    ("迷雾域", "诗域"):    (InteractionLevel.INTENDED,    "诗变为不连贯"),
    ("迷雾域", "信任域"):  (InteractionLevel.FORBIDDEN,   "信任系统失效"),
    ("迷雾域", "自我域"):  (InteractionLevel.INTENDED,    "MBTI返回undefined"),
}

# Emergent strategy detection rules
EMERGENT_RULES: dict[EmergentStrategy, dict[str, Any]] = {
    EmergentStrategy.POETRY_REFUGE: {
        "trigger": "consecutive_visits(诗域, >=3) AND career_context_present",
        "description": "反复进入诗域逃避职业域压力",
        "risk": "诗域内容消耗过快",
    },
    EmergentStrategy.TRUST_FARMING: {
        "trigger": "consecutive_positive_choices(信任域, >=3)",
        "description": "反复做信任域的正确选择获取高分",
        "risk": "需设计'正确但无意义'的惩罚",
    },
    EmergentStrategy.UNKNOWN_SPEEDRUN: {
        "trigger": "only_visits(迷雾域) AND skipped_others >=3",
        "description": "只走迷雾域，跳过其他域——最接近真相但最孤独",
        "risk": "需确保迷雾域独立可通",
    },
    EmergentStrategy.MBTI_REJECTOR: {
        "trigger": "rejected_labels_in(自我域, >=2)",
        "description": "在自我域拒绝一切标签——触发拒绝者隐藏路径",
        "risk": "需确保拒绝有叙事后果",
    },
    EmergentStrategy.CROSS_DOMAIN_HACKER: {
        "trigger": "echo_chain_length >=3",
        "description": "利用跨域回声机制连锁触发——奖励系统性思维",
        "risk": "需防回声泛滥",
    },
}

# Navigator response modifiers for each domain crossing
DOMAIN_CROSSING_NARRATIVES: dict[str, str] = {
    "信任域→迷雾域": (
        "Navigator 明显不安，信任分开始剧烈波动。它喃喃自语："
        "'这个区域的数据……我不——我无法验证。'"
    ),
    "迷雾域→信任域": (
        "信任系统的评分面板闪烁了几下，显示——ERROR。"
        "Navigator 沉默了很久，然后低声说：'有些事情，信任系统不配评判。'"
    ),
    "诗域→职业域": (
        "你在诗域留下的意象渗入了职业域的JD——"
        "那些工作描述突然变得有了灵魂，但也变得更不确定了。"
    ),
    "职业域→诗域": (
        "诗域的墙上出现了新的诗碎片——关于工作的疲惫，"
        "关于'钱多'的代价。那些词句似乎认得你。"
    ),
    "自我域→迷雾域": (
        "进入迷雾域的瞬间，你的MBTI标签暂时消失了。"
        "Navigator 低声说：'你刚才没有类型的时候……看起来更放松。'"
    ),
}


# ===== Tuning Values (GDD §4.3) =====
class Tuning:
    IMPRINT_PER_CHOICE_BASE = 2
    IMPRINT_PER_CHOICE_MIN = 1
    IMPRINT_PER_CHOICE_MAX = 5
    ECHO_THRESHOLD_SINGLE_AXIS = 8       # 单轴 >=8 触发回声
    ECHO_PER_SESSION_MAX = 2
    ECHO_COOLDOWN_SESSIONS = 2            # 同一域对回声间隔 >=2 会话
    EMERGENT_STRATEGY_DETECTION_DELAY = 3  # 连续 N 次检测到才触发


# ---------------------------------------------------------------------------
# In-memory state store (backed by DB when persistence is enabled)
# ---------------------------------------------------------------------------

@dataclass
class ValueImprintState:
    """Per-user invisible value imprint accumulator."""
    survival: int = 0
    freedom: int = 0
    belonging: int = 0

    def add(self, axis: str, points: int = 0):
        points = points or Tuning.IMPRINT_PER_CHOICE_BASE
        points = max(Tuning.IMPRINT_PER_CHOICE_MIN, min(Tuning.IMPRINT_PER_CHOICE_MAX, points))
        if axis == "survival":
            self.survival += points
        elif axis == "freedom":
            self.freedom += points
        elif axis == "belonging":
            self.belonging += points

    def get(self, axis: str) -> int:
        return getattr(self, axis, 0)

    def total(self) -> int:
        return self.survival + self.freedom + self.belonging

    def dominant_axis(self) -> str:
        m = max(self.survival, self.freedom, self.belonging)
        if m == 0:
            return "none"
        if self.survival == m:
            return "survival"
        if self.freedom == m:
            return "freedom"
        return "belonging"

    def is_balanced(self, threshold: int = 5) -> bool:
        """Check if all three axes are within `threshold` of each other."""
        vals = [self.survival, self.freedom, self.belonging]
        return max(vals) - min(vals) <= threshold and min(vals) > 0

    def is_extreme(self, threshold: int = 15) -> str | None:
        """Return axis name if one axis dominates extremely."""
        for axis, val in [("survival", self.survival), ("freedom", self.freedom), ("belonging", self.belonging)]:
            others = [v for a, v in [("s", self.survival), ("f", self.freedom), ("b", self.belonging)]]
            others.remove(val)
            if val >= threshold and val > sum(others):
                return axis
        return None

    def to_dict(self) -> dict:
        return {"survival": self.survival, "freedom": self.freedom, "belonging": self.belonging}


@dataclass
class DomainHistory:
    """Track user's domain visit history for a single session."""
    visited_domains: list[str] = field(default_factory=list)
    domain_choices: list[dict] = field(default_factory=list)  # [{domain, choice, timestamp}]
    echo_chain_length: int = 0

    def enter(self, domain: str):
        self.visited_domains.append(domain)

    def record_choice(self, domain: str, choice: str):
        import time
        self.domain_choices.append({"domain": domain, "choice": choice, "ts": time.time()})

    def last_domain(self) -> str | None:
        return self.visited_domains[-1] if self.visited_domains else None

    def previous_domain(self) -> str | None:
        return self.visited_domains[-2] if len(self.visited_domains) >= 2 else None


# ---------------------------------------------------------------------------
# Domain Engine
# ---------------------------------------------------------------------------

class DomainEngine:
    """Central game logic engine for Navigator's six-domain system.

    Responsibilities:
      - Evaluate cross-domain interaction rules (6×6 matrix)
      - Accumulate invisible value imprints
      - Detect cross-domain echo triggers
      - Detect emergent player strategies
    """

    def __init__(self, db=None):
        self._db = db
        self._imprints: dict[str, ValueImprintState] = {}       # user_id → state
        self._histories: dict[str, DomainHistory] = {}          # session_id → history
        self._user_histories: dict[str, list[str]] = {}         # user_id → [session_ids]
        self._echo_cooldowns: dict[str, dict[str, int]] = {}    # user_id → {pair_key: sessions_ago}
        self._strategy_detected: dict[str, set[EmergentStrategy]] = {}  # user_id → strategies

    # ---- 6×6 Matrix Query ----

    def get_interaction(self, source_domain: str, target_domain: str
                        ) -> tuple[InteractionLevel, str] | None:
        """Query the 6×6 matrix for a domain pair."""
        if source_domain == target_domain:
            return None
        return INTERACTION_MATRIX.get((source_domain, target_domain))

    def is_interaction_forbidden(self, source: str, target: str) -> bool:
        """Check if crossing from source to target is FORBIDDEN."""
        result = self.get_interaction(source, target)
        return result is not None and result[0] == InteractionLevel.FORBIDDEN

    def get_crossing_narrative(self, source: str, target: str) -> str | None:
        """Get the narrative text for a specific domain crossing."""
        key = f"{source}→{target}"
        return DOMAIN_CROSSING_NARRATIVES.get(key)

    # ---- Value Imprint ----

    def get_imprint(self, user_id: str) -> ValueImprintState:
        """Get or create imprint state for a user."""
        if user_id not in self._imprints:
            self._imprints[user_id] = ValueImprintState()
            # Try loading from DB
            if self._db:
                try:
                    rows = self._db.get_value_imprints(user_id)
                    if rows:
                        self._imprints[user_id].survival = rows.get("survival", 0)
                        self._imprints[user_id].freedom = rows.get("freedom", 0)
                        self._imprints[user_id].belonging = rows.get("belonging", 0)
                except Exception:
                    pass
        return self._imprints[user_id]

    def add_imprint(self, user_id: str, domain: str, points: int = 0, axis: str | None = None) -> dict:
        """Record a value imprint on the choice's own axis.

        ``axis`` is the option's imprint_axis. The domain's primary axis is only
        a fallback when the choice did not name one. Returns
        {'axis': str, 'added': int, 'total': dict}.
        """
        if not user_id:
            return {"axis": None, "added": 0, "total": {}}
        if axis not in ("survival", "freedom", "belonging"):
            axis = DOMAIN_AXIS.get(domain, "freedom")
        imprint = self.get_imprint(user_id)
        added = int(points or Tuning.IMPRINT_PER_CHOICE_BASE)
        added = max(Tuning.IMPRINT_PER_CHOICE_MIN, min(Tuning.IMPRINT_PER_CHOICE_MAX, added))
        imprint.add(axis, added)

        # Persist to DB
        if self._db:
            try:
                self._db.save_value_imprints(user_id, imprint.to_dict())
            except Exception:
                pass

        logger.debug(f"ValueImprint: user={user_id} axis={axis} +{added} "
                     f"→ total={imprint.to_dict()}")
        return {"axis": axis, "added": added, "total": imprint.to_dict()}

    # ---- Domain History ----

    def get_history(self, session_id: str) -> DomainHistory:
        """Get or create domain history for a session."""
        if session_id not in self._histories:
            self._histories[session_id] = DomainHistory()
        return self._histories[session_id]

    def record_domain_enter(self, user_id: str, session_id: str, domain: str) -> dict | None:
        """Record domain entry and check cross-domain effects.

        Returns a dict with echo/crossing effects if any, or None.
        """
        history = self.get_history(session_id)
        previous = history.last_domain()
        history.enter(domain)

        # Track user history
        if user_id not in self._user_histories:
            self._user_histories[user_id] = []
        if session_id not in self._user_histories[user_id]:
            self._user_histories[user_id].append(session_id)

        result: dict = {
            "domain": domain,
            "previous_domain": previous,
            "is_first_visit": domain not in history.visited_domains[:-1],
            "echo": None,
            "crossing_narrative": None,
            "interaction_level": None,
            "forbidden_detected": False,
        }

        # Check cross-domain interaction
        if previous and previous != domain:
            interaction = self.get_interaction(previous, domain)
            if interaction:
                level, desc = interaction
                result["interaction_level"] = level.value
                result["interaction_effect"] = desc
                result["crossing_narrative"] = self.get_crossing_narrative(previous, domain)

                if level == InteractionLevel.FORBIDDEN:
                    result["forbidden_detected"] = True
                    logger.warning(f"FORBIDDEN interaction: {previous}→{domain} "
                                   f"user={user_id} session={session_id}")

        # Check echo trigger
        echo_result = self._check_echo(user_id, session_id)
        if echo_result:
            result["echo"] = echo_result

        return result

    def record_choice(self, session_id: str, domain: str, choice: str, user_id: str | None = None):
        """Record a choice made in a domain."""
        history = self.get_history(session_id)
        history.record_choice(domain, choice)

    # ---- Cross-Domain Echo ----

    def _check_echo(self, user_id: str, session_id: str) -> dict | None:
        """Check if an echo should trigger based on imprint thresholds."""
        if user_id not in self._imprints:
            return None

        imprint = self._imprints[user_id]
        history = self.get_history(session_id)
        current_domain = history.last_domain()

        # Check per-session cap
        if history.echo_chain_length >= Tuning.ECHO_PER_SESSION_MAX:
            logger.debug(f"Echo suppressed: session cap reached "
                         f"(session={session_id})")
            return None

        # Check cooldown for this domain pair
        previous = history.previous_domain()
        if previous and current_domain:
            pair_key = f"{previous}→{current_domain}"
            if user_id not in self._echo_cooldowns:
                self._echo_cooldowns[user_id] = {}
            if pair_key in self._echo_cooldowns[user_id]:
                if self._echo_cooldowns[user_id][pair_key] < Tuning.ECHO_COOLDOWN_SESSIONS:
                    logger.debug(f"Echo suppressed: cooldown for {pair_key}")
                    return None

        # Check axis thresholds
        dominant = imprint.dominant_axis()
        if dominant == "none":
            return None

        axis_val = imprint.get(dominant)
        if axis_val < Tuning.ECHO_THRESHOLD_SINGLE_AXIS:
            return None

        # Echo triggered!
        echo_type = self._select_echo_type(current_domain or "迷雾域", dominant)

        # Build echo event
        echo = {
            "echo_type": echo_type.value,
            "source_axis": dominant,
            "axis_value": axis_val,
            "target_domain": current_domain,
            "narrative_hint": self._echo_narrative(echo_type, dominant, current_domain),
            "chain_position": history.echo_chain_length + 1,
        }

        history.echo_chain_length += 1

        # Set cooldown
        if previous and current_domain:
            pair_key = f"{previous}→{current_domain}"
            if user_id not in self._echo_cooldowns:
                self._echo_cooldowns[user_id] = {}
            self._echo_cooldowns[user_id][pair_key] = 0

        logger.info(f"Echo triggered: {echo_type.value} user={user_id} "
                    f"axis={dominant}({axis_val}) → domain={current_domain}")
        return echo

    def _select_echo_type(self, domain: str, axis: str) -> EchoType:
        """Select echo type based on domain and axis context."""
        # Navigator echo for character-driven domains
        if domain in ("自我域", "身份域"):
            return EchoType.NAVIGATOR
        # Environment echo for poetic/spatial domains
        if domain in ("诗域", "迷雾域"):
            return EchoType.ENVIRONMENT
        # System echo for rules-driven domains
        if domain in ("信任域", "职业域"):
            return EchoType.SYSTEM
        return EchoType.CHARACTER

    def _echo_narrative(self, echo_type: EchoType, axis: str, domain: str) -> str:
        """Generate narrative hint text for an echo event."""
        axis_labels = {"survival": "生存", "freedom": "自由", "belonging": "归属"}

        hints = {
            (EchoType.CHARACTER, "survival"): f"在{domain}的角落，你看到了一个身影——似乎之前在职业域的面试间见过。",
            (EchoType.CHARACTER, "freedom"): f"{domain}里的一位NPC回头看了你一眼，她手中拿着你在诗域留下的字条。",
            (EchoType.CHARACTER, "belonging"): f"你在身份域认识的某个人，出现在了{domain}——他们似乎也在寻找什么。",
            (EchoType.ENVIRONMENT, "survival"): f"{domain}的墙壁上浮现出了职业域的工作描述——但它们在剥落、变形。",
            (EchoType.ENVIRONMENT, "freedom"): f"空气里漂浮着诗域的词语碎片。{domain}正在悄然改变它的调性。",
            (EchoType.ENVIRONMENT, "belonging"): f"地面映出了身份域的影像——仿佛两个域在重叠。",
            (EchoType.SYSTEM, "survival"): f"你的生存选择在{domain}的系统中留下了痕迹——某些选项被锁定了，另一些被解锁。",
            (EchoType.SYSTEM, "freedom"): f"系统在重新计算。你在自由轴上的累积正在改变{domain}的规则。",
            (EchoType.SYSTEM, "belonging"): f"{domain}的状态面板显示了一行新的注释：'来访者有未完成的羁绊。'",
            (EchoType.NAVIGATOR, "survival"): f"Navigator 顿了顿：'你之前在职业域做的那个选择……它一直在影响这里。'",
            (EchoType.NAVIGATOR, "freedom"): f"Navigator 轻声说：'你在诗域留下的那些话——它们并不只属于一个地方。'",
            (EchoType.NAVIGATOR, "belonging"): f"Navigator 看着你：'身份域不会忘记你回去过。{domain}也知道了。'",
        }

        key = (echo_type, axis)
        if key in hints:
            return hints[key]
        return f"一种微弱的共鸣感在{domain}中荡漾——你在{axis_labels.get(axis, axis)}轴上的选择正在回响。"

    # ---- Emergent Strategy Detection ----

    def detect_strategies(self, user_id: str) -> list[dict]:
        """Detect emergent player strategies. Returns list of triggered strategies."""
        if user_id not in self._imprints:
            return []

        history = self.get_history("latest")
        imprint = self._imprints[user_id]
        detected: list[dict] = []

        # Strategy 1: 诗域避难所 — 连续3次进入诗域且有职业域上下文
        if len(history.visited_domains) >= 3:
            last3 = history.visited_domains[-3:]
            if all(d == "诗域" for d in last3) and "职业域" in history.visited_domains:
                s = EmergentStrategy.POETRY_REFUGE
                detected.append({"strategy": s.value, **EMERGENT_RULES[s]})

        # Strategy 2: 信任域刷分 — 连续3次在信任域做"正面"选择
        trust_choices = [c for c in history.domain_choices if c["domain"] == "信任域"]
        if len(trust_choices) >= 3:
            positive_keywords = ["信任", "诚实", "坦白", "帮助", "支持"]
            positive_count = sum(
                1 for c in trust_choices[-3:]
                if any(kw in str(c["choice"]) for kw in positive_keywords)
            )
            if positive_count >= 3:
                s = EmergentStrategy.TRUST_FARMING
                detected.append({"strategy": s.value, **EMERGENT_RULES[s]})

        # Strategy 3: 迷雾域速通 — 只走迷雾域，跳过至少3个其他域
        unique = set(history.visited_domains)
        skipped = len(set(DOMAINS) - unique - {"迷雾域"})
        if len(unique) == 1 and "迷雾域" in unique and skipped >= 3:
            s = EmergentStrategy.UNKNOWN_SPEEDRUN
            detected.append({"strategy": s.value, **EMERGENT_RULES[s]})

        # Strategy 4: MBTI拒绝者 — 自我域拒绝标签至少2次
        reject_choices = [
            c for c in history.domain_choices
            if c["domain"] == "自我域" and any(
                kw in str(c["choice"]) for kw in ["拒绝", "不接受", "不认同", "不是我", "不对"]
            )
        ]
        if len(reject_choices) >= 2:
            s = EmergentStrategy.MBTI_REJECTOR
            detected.append({"strategy": s.value, **EMERGENT_RULES[s]})

        # Strategy 5: 跨域黑客 — 回声链长度 >=3
        if history.echo_chain_length >= 3:
            s = EmergentStrategy.CROSS_DOMAIN_HACKER
            detected.append({"strategy": s.value, **EMERGENT_RULES[s]})

        # Track detection
        if detected:
            if user_id not in self._strategy_detected:
                self._strategy_detected[user_id] = set()
            for d in detected:
                self._strategy_detected[user_id].add(
                    EmergentStrategy(d["strategy"])
                )

        return detected

    def get_active_strategies(self, user_id: str) -> list[str]:
        """Get all strategies previously detected for a user."""
        if user_id in self._strategy_detected:
            return [s.value for s in self._strategy_detected[user_id]]
        return []

    # ---- Navigator Context Injector ----

    def build_navigator_context(self, user_id: str, session_id: str) -> dict:
        """Build a full context dict for Navigator prompt injection.

        Returns a dict with all engine state for central_brain to inject
        into the Navigator conversation prompt.
        """
        imprint = self.get_imprint(user_id)
        history = self.get_history(session_id)
        strategies = self.get_active_strategies(user_id)

        ctx: dict = {
            "imprint": imprint.to_dict(),
            "imprint_total": imprint.total(),
            "dominant_axis": imprint.dominant_axis(),
            "is_balanced": imprint.is_balanced(),
            "is_extreme": imprint.is_extreme(),
            # Domain context
            "visited_domains": history.visited_domains[-5:],  # last 5
            "domain_count": len(set(history.visited_domains)),
            "current_domain": history.last_domain(),
            # Echo context
            "echo_chain_length": history.echo_chain_length,
            "echo_chain_active": history.echo_chain_length > 0,
            # Strategy context
            "active_strategies": strategies,
            # GDD Act stage estimation
            "estimated_act": self._estimate_act(imprint, history),
        }

        return ctx

    def _estimate_act(self, imprint: ValueImprintState, history: DomainHistory) -> int:
        """Estimate which Act the player is in based on imprint & exploration."""
        unique_domains = len(set(history.visited_domains))
        total = imprint.total()

        if unique_domains <= 1 and total < 5:
            return 1  # Act 1: Landing
        if unique_domains <= 5 and total < 15:
            return 2  # Act 2: Wandering
        if unique_domains >= 5 and total < 25:
            return 3  # Act 3: Deep Dive
        if total >= 25 and imprint.is_extreme():
            return 4  # Act 4: The Fog
        if total >= 30:
            return 5  # Act 5: Reckoning
        return 1  # Default: Act 1

    # ---- Session Management ----

    def end_session(self, user_id: str, session_id: str):
        """Clean up session state."""
        # Decrement cooldown counters
        if user_id in self._echo_cooldowns:
            for pair_key in list(self._echo_cooldowns[user_id]):
                self._echo_cooldowns[user_id][pair_key] += 1
                if self._echo_cooldowns[user_id][pair_key] > 10:
                    del self._echo_cooldowns[user_id][pair_key]

        logger.info(f"DomainEngine session ended: user={user_id} session={session_id}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine: DomainEngine | None = None


def get_domain_engine(db=None) -> DomainEngine:
    """Get or create the singleton DomainEngine instance."""
    global _engine
    if _engine is None:
        _engine = DomainEngine(db=db)
    return _engine


def reset_engine():
    """Reset engine state (for testing)."""
    global _engine
    _engine = None
