"""
Game routes blueprint.
Ownership: Jason

Endpoints (PlanetX 小程序 - 舰队/人格):
  POST /v1/game/profile-sync    - Sync personality result
  GET  /v1/game/profile         - Get game profile (personality + XP + level)
  POST /v1/game/mission-complete- Complete a mission, earn XP
  POST /v1/game/match           - 1:1 fleet match by personality (v0 rules)
  POST /v1/game/fleet/create    - Create a fleet
  POST /v1/game/fleet/join      - Join a fleet
  GET  /v1/game/fleet/mine      - Get my fleet
  POST /v1/game/fleet/leave     - Leave current fleet

Endpoints (HarmonyOS 元服务 - 答题游戏):
  POST /v1/game/start           - Start a new quiz session
  POST /v1/game/answer          - Submit an answer
  GET  /v1/game/result          - Get quiz result by session_id
  GET  /v1/game/history         - Get user's quiz history
"""
import hashlib
import hmac
import json as _json
import math
from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth, optional_auth
from src.agents.trust_agent import generate_attestations
from src.signal_bridge.gfcc_fanout import send_gfcc_personality_beacon
import logging

logger = logging.getLogger("looma.game_routes")

game_bp = Blueprint("game", __name__)


def _get_db():
    return current_app._db


# ── XP / Level helpers ──

def _calculate_level(xp: int) -> int:
    """Level formula: level = floor(sqrt(xp / 100)) + 1.
    Every 100 XP ≈ 1 level at low levels, slows naturally."""
    return int(math.sqrt(xp / 100)) + 1 if xp > 0 else 1


# ── Match helpers (PlanetX 域内 v0 规则配对) ──

PERSONALITY_EMOJI = {
    "星云艺术家": "🎨",
    "黑洞程序员": "💻",
    "超新星领航员": "⭐",
    "双星星系守护者": "🌓",
    "脉冲星修行者": "✨",
    "暗物质漫游者": "🌌",
}

# 互补人格：创造力↔深度、行动↔节奏、守护↔自由
COMPLEMENTARY_PERSONALITY = {
    "星云艺术家": "黑洞程序员",
    "黑洞程序员": "星云艺术家",
    "超新星领航员": "脉冲星修行者",
    "脉冲星修行者": "超新星领航员",
    "双星星系守护者": "暗物质漫游者",
    "暗物质漫游者": "双星星系守护者",
}

MATCH_REASON = {
    ("星云艺术家", "黑洞程序员"): "人格互补 · 创造力遇见深度逻辑",
    ("黑洞程序员", "星云艺术家"): "人格互补 · 深度逻辑遇见创造力",
    ("超新星领航员", "脉冲星修行者"): "人格互补 · 行动力遇见长期节奏",
    ("脉冲星修行者", "超新星领航员"): "人格互补 · 长期节奏遇见行动力",
    ("双星星系守护者", "暗物质漫游者"): "人格互补 · 安全感遇见自由引力",
    ("暗物质漫游者", "双星星系守护者"): "人格互补 · 自由引力遇见安全感",
}


def _score_personality_pair(self_type: str, other_type: str) -> tuple[int, str]:
    """Score a candidate pair. Returns (score 0-100, reason)."""
    if not other_type:
        return 0, "对方尚未完成人格测试"
    if COMPLEMENTARY_PERSONALITY.get(self_type) == other_type:
        reason = MATCH_REASON.get((self_type, other_type), "人格互补 · 舰队内最佳配对")
        return 95, reason
    if self_type and self_type == other_type:
        return 72, f"同频共振 · 你们都是「{self_type}」"
    if self_type and other_type:
        return 58, f"舰队共鸣 · 「{self_type}」×「{other_type}」"
    return 40, "舰队初遇 · 继续探索彼此轨道"


# ── Personality & Profile ──

# Valid PlanetX identity choices (onboarding)
_PLANETX_IDENTITIES = frozenset({"explorer", "captain", "wanderer"})


@game_bp.route("/profile-sync", methods=["POST"])
@require_auth
def sync_personality():
    """Sync personality test result and/or PlanetX identity to looma backend."""
    data = request.get_json() or {}
    personality_type = (data.get("personality_type") or "").strip()
    personality_detail = data.get("personality_detail", "")
    identity = (data.get("identity") or "").strip()

    if identity and identity not in _PLANETX_IDENTITIES:
        return jsonify(
            error="bad_request",
            message="identity must be explorer, captain, or wanderer",
        ), 400

    if not personality_type and not identity:
        return jsonify(
            error="bad_request",
            message="personality_type or identity required",
        ), 400

    db = _get_db()
    if identity:
        db.update_game_identity(g.user_id, identity)
    if personality_type:
        db.upsert_game_profile(g.user_id, personality_type, personality_detail)

        # ── Signal Bridge 3 egress (best-effort, non-blocking) ──
        try:
            _send_personality_beacon(db, g.user_id, personality_type, personality_detail)
        except Exception as e:
            logger.warning("personality_beacon: egress hook failed for %s: %s", g.user_id, e)

        from src.analytics.events import log_product_event, platform_from_request
        log_product_event(
            db,
            "quiz_complete",
            user_id=g.user_id,
            platform=platform_from_request(request),
            source="server",
            properties={"personality_type": personality_type},
        )

        # ── Trust Agent: record quiz memory ──
        try:
            db.insert_trust_memory(
                user_id=g.user_id,
                session_type="quiz",
                session_id=f"profile_sync_{g.user_id}",
                memory_content={
                    "personality_type": personality_type,
                    "personality_detail": personality_detail,
                },
                memory_level=2,
            )
            generate_attestations(g.user_id, db)
        except Exception as e:
            logger.warning("trust_agent: quiz memory skipped for %s: %s", g.user_id, e)

    # Return the full profile after sync (so frontend gets XP/level too)
    profile = db.get_game_profile(g.user_id)
    return jsonify(
        message="profile synced",
        personality_type=profile.get("personality_type") or "",
        identity=profile.get("identity") or "",
        xp=profile["xp"],
        level=profile["level"],
    )


@game_bp.route("/profile", methods=["GET"])
@require_auth
def get_game_profile():
    """Get current user's game profile (personality + XP + level)."""
    db = _get_db()
    profile = db.get_game_profile(g.user_id)
    if not profile:
        # Return default profile for new users (not an error)
        # Still include fleet data for users who are in a fleet
        user_fleet = db.get_user_fleet(g.user_id)
        fleet = dict(user_fleet) if user_fleet else None
        team_size = 0
        fleet_members = []
        if fleet:
            members = db.get_fleet_members(fleet["id"])
            team_size = len(members)
            fleet_members = [m["user_id"] for m in members]
        return jsonify(
            id=None,
            user_id=g.user_id,
            identity="",
            personality_type="",
            personality_detail="",
            xp=0,
            level=1,
            xp_to_next=100,
            missions_completed=[],
            total_mission_xp=0,
            updated_at=None,
            fleet=fleet,
            team_size=team_size,
            fleet_members=fleet_members,
        )

    # Compute current level from XP (level column may be stale)
    computed_level = _calculate_level(profile["xp"])
    if computed_level != profile["level"]:
        db.update_level(g.user_id, computed_level)
        profile["level"] = computed_level

    missions = db.get_user_missions(g.user_id)
    mission_ids = [m["mission_id"] for m in missions]
    total_mission_xp = sum(m["xp_reward"] for m in missions)
    xp = profile["xp"]
    level = profile["level"]
    xp_to_next = max(100, (level ** 2) * 100 - xp)

    # Fleet data (attached to profile for frontend state hydration)
    user_fleet = db.get_user_fleet(g.user_id)
    fleet = None
    team_size = 0
    fleet_members = []
    if user_fleet:
        fleet = dict(user_fleet)
        members = db.get_fleet_members(fleet["id"])
        team_size = len(members)
        fleet_members = [m["user_id"] for m in members]

    return jsonify(
        id=profile["id"],
        user_id=profile["user_id"],
        identity=profile.get("identity") or "",
        personality_type=profile["personality_type"],
        personality_detail=profile["personality_detail"],
        xp=xp,
        level=level,
        xp_to_next=xp_to_next,
        missions_completed=mission_ids,
        total_mission_xp=total_mission_xp,
        updated_at=profile["updated_at"],
        fleet=fleet,
        team_size=team_size,
        fleet_members=fleet_members,
    )


# ── Mission ──

@game_bp.route("/mission-complete", methods=["POST"])
@require_auth
def complete_mission():
    """Complete a mission and earn XP. No double-completion allowed."""
    data = request.get_json() or {}
    mission_id = data.get("mission_id", "")
    xp_reward = int(data.get("xp_reward", 10))

    if not mission_id:
        return jsonify(error="bad_request", message="mission_id required"), 400

    if xp_reward < 0:
        return jsonify(error="bad_request", message="xp_reward must be non-negative"), 400

    db = _get_db()

    # Ensure user has a game profile (create stub if none)
    profile = db.get_game_profile(g.user_id)
    if not profile:
        db.upsert_game_profile(g.user_id, "", "")
        profile = db.get_game_profile(g.user_id)

    completion_id, was_new = db.complete_mission(g.user_id, mission_id, xp_reward)

    if not was_new:
        return jsonify(
            error="already_completed",
            message=f"Mission {mission_id} already completed",
        ), 409

    # Refresh profile to get updated XP
    # NOTE: db.complete_mission already added xp_reward to the profile, so
    # profile["xp"] is the new total. Don't add xp_reward again.
    profile = db.get_game_profile(g.user_id)
    new_level = _calculate_level(profile["xp"])
    if new_level != profile["level"]:
        db.update_level(g.user_id, new_level)

    return jsonify(
        message="mission completed",
        mission_id=mission_id,
        xp_earned=xp_reward,
        total_xp=profile["xp"],
        level=new_level,
    )


# ── Match (PlanetX 域内 1:1) ──

@game_bp.route("/match", methods=["POST"])
@require_auth
def fleet_match():
    """Match current user 1:1 with a fleet member by personality complementarity.

    v0 rules (replaceable by trained model later):
      - Must be in a fleet with ≥1 other member
      - Prefer complementary personality; else same-type; else best available
      - Does NOT complete the match mission — caller must POST mission-complete
    """
    db = _get_db()
    profile = db.get_game_profile(g.user_id)
    if not profile or not (profile.get("personality_type") or "").strip():
        return jsonify(
            error="personality_required",
            message="请先完成星际人格测试",
        ), 400

    self_type = (profile.get("personality_type") or "").strip()
    fleet = db.get_user_fleet(g.user_id)
    if not fleet:
        return jsonify(
            error="fleet_required",
            message="请先加入或创建舰队",
        ), 400

    members = db.get_fleet_members(fleet["id"])
    other_ids = [m["user_id"] for m in members if m["user_id"] != g.user_id]
    if not other_ids:
        return jsonify(
            error="fleet_too_small",
            message="舰队内暂无其他成员可匹配",
        ), 400

    candidates = db.get_game_profiles_for_users(other_ids)
    # Prefer members who finished personality; still allow fallback to bare members
    by_id = {c["user_id"]: c for c in candidates}
    scored = []
    for uid in other_ids:
        cand = by_id.get(uid)
        other_type = (cand.get("personality_type") or "").strip() if cand else ""
        score, reason = _score_personality_pair(self_type, other_type)
        display_name = ""
        if cand:
            display_name = (cand.get("display_name") or "").strip()
        if not display_name:
            # fall back to fleet member join row
            member_row = next((m for m in members if m["user_id"] == uid), None)
            display_name = (member_row.get("name") or "神秘星际公民") if member_row else "神秘星际公民"
        scored.append({
            "user_id": uid,
            "name": display_name or "神秘星际公民",
            "personality_type": other_type or "未觉醒",
            "personality_emoji": PERSONALITY_EMOJI.get(other_type, "🪐"),
            "match_score": score,
            "reason": reason,
        })

    scored.sort(key=lambda x: (-x["match_score"], x["user_id"]))
    best = scored[0]

    return jsonify({
        "matched": True,
        "match": best,
        "self": {
            "user_id": g.user_id,
            "personality_type": self_type,
            "personality_emoji": PERSONALITY_EMOJI.get(self_type, "🪐"),
        },
        "fleet_id": fleet["id"],
        "fleet_name": fleet["name"],
        "candidates_considered": len(scored),
    })


# ── Fleet ──

@game_bp.route("/fleet/create", methods=["POST"])
@require_auth
def create_fleet():
    """Create a new fleet. Creator becomes captain + auto-joins.
    Returns invite_code for sharing."""
    data = request.get_json() or {}
    name = data.get("name", "")
    description = data.get("description", "")

    if not name:
        return jsonify(error="bad_request", message="fleet name required"), 400

    if len(name) > 50:
        return jsonify(error="bad_request", message="fleet name too long (max 50)"), 400

    db = _get_db()

    # Check user not already in a fleet (MVP: one fleet per user)
    existing_fleet = db.get_user_fleet(g.user_id)
    if existing_fleet:
        return jsonify(
            error="already_in_fleet",
            message=f"User already in fleet '{existing_fleet['name']}'",
            fleet_id=existing_fleet["id"],
        ), 409

    fleet_id = db.create_fleet(g.user_id, name, description)
    fleet = db.get_fleet_by_id(fleet_id)
    members = db.get_fleet_members(fleet_id)

    # ── Trust Agent: record fleet creation memory ──
    try:
        db.insert_trust_memory(
            user_id=g.user_id,
            session_type="fleet",
            session_id=fleet_id,
            memory_content={
                "action": "create_fleet",
                "fleet_name": name,
                "consensus_confirmed": True,
            },
            memory_level=2,
        )
        generate_attestations(g.user_id, db)
    except Exception as e:
        logger.warning("trust_agent: fleet create memory skipped for %s: %s", g.user_id, e)

    return jsonify(
        id=fleet["id"],
        name=fleet["name"],
        captain_id=fleet["captain_id"],
        description=fleet["description"],
        invite_code=fleet["invite_code"],
        member_count=len(members),
        team_size=len(members),
        created_at=fleet["created_at"],
    ), 201


@game_bp.route("/fleet/join", methods=["POST"])
@require_auth
def join_fleet():
    """Join an existing fleet by fleet_id or invite_code."""
    data = request.get_json() or {}
    fleet_id = data.get("fleet_id", "") or data.get("invite_code", "")

    if not fleet_id:
        return jsonify(error="bad_request", message="fleet_id or invite_code required"), 400

    db = _get_db()

    # Resolve invite_code → fleet_id if needed
    # fleet_id is a UUID (36 chars), invite_code is 8 chars uppercase
    if len(fleet_id) <= 12:
        fleet = db.get_fleet_by_invite_code(fleet_id)
        if not fleet:
            return jsonify(error="not_found", message="舰队邀请码不存在"), 404
        fleet_id = fleet["id"]

    try:
        db.join_fleet(fleet_id, g.user_id)
    except ValueError as e:
        msg = str(e)
        if "does not exist" in msg:
            return jsonify(error="not_found", message=msg), 404
        if "already in fleet" in msg:
            existing = db.get_user_fleet(g.user_id)
            return jsonify(
                error="already_in_fleet",
                message=msg,
                current_fleet_id=existing["id"] if existing else None,
            ), 409
        return jsonify(error="bad_request", message=msg), 400

    fleet = db.get_fleet_by_id(fleet_id)
    members = db.get_fleet_members(fleet_id)

    # ── Trust Agent: record fleet join memory ──
    try:
        db.insert_trust_memory(
            user_id=g.user_id,
            session_type="fleet",
            session_id=fleet_id,
            memory_content={
                "action": "join_fleet",
                "fleet_name": fleet["name"],
                "consensus_confirmed": True,
            },
            memory_level=1,
        )
        generate_attestations(g.user_id, db)
    except Exception as e:
        logger.warning("trust_agent: fleet join memory skipped for %s: %s", g.user_id, e)

    return jsonify(
        message="joined fleet",
        fleet=fleet,
        fleet_id=fleet_id,
        fleet_name=fleet["name"],
        captain_id=fleet["captain_id"],
        team_size=len(members),
        fleet_members=[m["user_id"] for m in members],
        member_count=len(members),
    )


@game_bp.route("/fleet/mine", methods=["GET"])
@require_auth
def my_fleet():
    """Get the fleet the current user belongs to, with member list."""
    db = _get_db()
    fleet = db.get_user_fleet(g.user_id)

    if not fleet:
        return jsonify(fleet=None, team_size=0, fleet_members=[], message="not in any fleet"), 200

    members = db.get_fleet_members(fleet["id"])

    return jsonify(
        fleet=dict(fleet),
        members=members,
        team_size=len(members),
        fleet_members=[m["user_id"] for m in members],
        member_count=len(members),
    )


@game_bp.route("/fleet/leave", methods=["POST"])
@require_auth
def leave_fleet():
    """Leave current fleet. Captain cannot leave — must dissolve."""
    db = _get_db()

    try:
        db.leave_fleet(g.user_id)
    except ValueError as e:
        msg = str(e)
        if "Captain cannot leave" in msg:
            return jsonify(
                error="captain_cannot_leave",
                message="As captain, you must dissolve the fleet instead of leaving",
            ), 403
        return jsonify(error="bad_request", message=msg), 400

    return jsonify(message="left fleet")


# ── Quiz Game (HarmonyOS 元服务 答题游戏) ──

# Mock question bank — 前端未连接真实题库时的 fallback
MOCK_QUIZ_QUESTIONS = [
    {
        "id": "q1", "text": "HarmonyOS 的 UI 框架叫什么？", "type": "single", "order": 1,
        "options": [
            {"id": "a", "text": "ArkUI", "value": 10},
            {"id": "b", "text": "React Native", "value": 0},
            {"id": "c", "text": "Flutter", "value": 0},
            {"id": "d", "text": "SwiftUI", "value": 0},
        ],
    },
    {
        "id": "q2", "text": "@State 装饰器的作用是什么？", "type": "single", "order": 2,
        "options": [
            {"id": "a", "text": "声明组件内部状态，变化时自动刷新 UI", "value": 10},
            {"id": "b", "text": "声明全局常量", "value": 0},
            {"id": "c", "text": "定义路由参数", "value": 0},
            {"id": "d", "text": "创建网络请求", "value": 0},
        ],
    },
    {
        "id": "q3", "text": "哪种数据结构是 FIFO（先进先出）？", "type": "single", "order": 3,
        "options": [
            {"id": "a", "text": "队列 (Queue)", "value": 10},
            {"id": "b", "text": "栈 (Stack)", "value": 0},
            {"id": "c", "text": "堆 (Heap)", "value": 0},
            {"id": "d", "text": "二叉树 (Binary Tree)", "value": 0},
        ],
    },
    {
        "id": "q4", "text": "以下哪个是 Looma 后端使用的 Web 框架？", "type": "single", "order": 4,
        "options": [
            {"id": "a", "text": "Flask (Python)", "value": 10},
            {"id": "b", "text": "Express (Node.js)", "value": 0},
            {"id": "c", "text": "Spring Boot (Java)", "value": 0},
            {"id": "d", "text": "Gin (Go)", "value": 0},
        ],
    },
    {
        "id": "q5", "text": "SQLite 的 WAL 模式主要优势是什么？", "type": "single", "order": 5,
        "options": [
            {"id": "a", "text": "支持并发读写，读不阻塞写", "value": 10},
            {"id": "b", "text": "数据加密存储", "value": 0},
            {"id": "c", "text": "自动备份到云端", "value": 0},
            {"id": "d", "text": "支持分布式查询", "value": 0},
        ],
    },
]


def _score_answer(question: dict, selected_ids: list[str]) -> int:
    """Calculate score for a single question based on selected options."""
    options = question.get("options", [])
    if not options:
        return 0
    score = 0
    for opt in options:
        if opt["id"] in selected_ids:
            score += opt.get("value", 0)
    return score


def _explain_answer(question: dict, selected_ids: list[str]) -> str:
    """Generate a simple explanation based on correct/incorrect options."""
    options = question.get("options", [])
    correct_opts = [o["text"] for o in options if o.get("value", 0) > 0]
    if not correct_opts:
        return "请查看答案解析。"
    return f"正确答案是: {', '.join(correct_opts)}"


@game_bp.route("/start", methods=["POST"])
@require_auth
def quiz_start():
    """Start a new quiz session. Returns session_id + questions."""
    db = _get_db()

    import json as _json
    questions_json = _json.dumps(MOCK_QUIZ_QUESTIONS, ensure_ascii=False)
    session = db.create_quiz_session(g.user_id, questions_json)

    return jsonify(
        session_id=session["id"],
        questions=MOCK_QUIZ_QUESTIONS,
        total=len(MOCK_QUIZ_QUESTIONS),
    ), 201


@game_bp.route("/answer", methods=["POST"])
@require_auth
def quiz_answer():
    """Submit an answer for the current question.
    
    Body: { "session_id": "...", "question_id": "...", "option_ids": [...] }
    Returns: { correct, score, explanation, next_question?, completed }
    """
    data = request.get_json() or {}
    session_id = (data.get("session_id") or "").strip()
    question_id = (data.get("question_id") or "").strip()
    option_ids = data.get("option_ids", [])

    if not session_id:
        return jsonify(error="bad_request", message="session_id required"), 400
    if not question_id:
        return jsonify(error="bad_request", message="question_id required"), 400

    db = _get_db()
    session = db.get_quiz_session(session_id)
    if not session:
        return jsonify(error="not_found", message="quiz session not found"), 404
    import json as _json
    if session["user_id"] != g.user_id:
        return jsonify(error="forbidden", message="not your session"), 403

    questions = _json.loads(session["questions_json"])
    current_q = None
    for q in questions:
        if q["id"] == question_id:
            current_q = q
            break

    if not current_q:
        return jsonify(error="bad_request", message="question not in this session"), 400

    score = _score_answer(current_q, option_ids)
    updated = db.submit_quiz_answer(session_id, question_id, option_ids, score)
    if not updated:
        return jsonify(error="server_error", message="failed to record answer"), 500

    is_completed = updated["status"] == "completed"
    explanation = _explain_answer(current_q, option_ids)

    next_q = None
    if not is_completed:
        next_index = updated["current_index"]
        if next_index < len(questions):
            next_q = questions[next_index]

    response = {
        "correct": score > 0,
        "score": score,
        "explanation": explanation,
        "completed": is_completed,
    }
    if next_q:
        response["next_question"] = next_q

    return jsonify(response)


@game_bp.route("/result", methods=["GET"])
@require_auth
def quiz_result():
    """Get result for a completed quiz session.

    Query: ?session_id=xxx
    """
    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return jsonify(error="bad_request", message="session_id required"), 400

    db = _get_db()
    session = db.get_quiz_session(session_id)
    if not session:
        return jsonify(error="not_found", message="quiz session not found"), 404
    import json as _json
    if session["user_id"] != g.user_id:
        return jsonify(error="forbidden", message="not your session"), 403

    # Auto-complete if still active (last answer submitted but session not closed)
    if session["status"] != "completed":
        # Determine result_type from score percentage
        total = session["total_questions"] or 1
        pct = session["total_score"] / (total * 10) if total > 0 else 0
        result_type = "专家级" if pct >= 0.8 else ("进阶者" if pct >= 0.5 else "初学者")
        insights = [
            f"答对 {session['correct_count']}/{session['total_questions']} 题",
            f"总得分 {session['total_score']} 分",
        ]
        session = db.complete_quiz_session(
            session_id,
            result_type=result_type,
            insights_json=_json.dumps(insights, ensure_ascii=False),
        )

        # ── Trust Agent: record HarmonyOS quiz completion ──
        try:
            db.insert_trust_memory(
                user_id=g.user_id,
                session_type="quiz",
                session_id=session_id,
                memory_content={
                    "result_type": result_type,
                    "total_score": session["total_score"],
                    "correct_count": session["correct_count"],
                    "total_questions": session["total_questions"],
                },
                memory_level=1,
            )
            generate_attestations(g.user_id, db)
        except Exception as e:
            logger.warning("trust_agent: harmonyos quiz memory skipped for %s: %s", g.user_id, e)
    import json as _json
    insights = _json.loads(session.get("insights_json") or "[]")

    return jsonify(
        session_id=session["id"],
        total_score=session["total_score"],
        total_questions=session["total_questions"],
        correct_count=session["correct_count"],
        result_type=session.get("result_type") or "",
        insights=insights,
    )


@game_bp.route("/history", methods=["GET"])
@require_auth
def quiz_history():
    """Get user's quiz session history."""
    db = _get_db()
    records = db.get_quiz_history(g.user_id)
    return jsonify(sessions=records, total=len(records))


# ── Signal Bridge 2/3 inbound (HMAC + idempotency) ──

_MATCH_MISSION_ID = "match"
_MATCH_MISSION_XP = 50  # 种子期固定奖励；后续可改从 data.match_score 推导


def _verify_signal_signature() -> bool:
    """Verify X-Signal-Signature = HMAC-SHA256(raw_body, SIGNAL_BRIDGE_SECRET).

    Uses raw request body bytes (not re-serialized JSON) so the digest matches
    exactly what the sender computed over the transmitted payload.
    """
    secret = current_app.config.get("SIGNAL_BRIDGE_SECRET", "")
    if not secret:
        logger.warning("SIGNAL_BRIDGE_SECRET not configured; rejecting signal ingest")
        return False
    body = request.get_data()
    signature = request.headers.get("X-Signal-Signature", "")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


@game_bp.route("/signal-ingest", methods=["POST"])
def signal_ingest():
    """Bridge 2/3 inbound endpoint (no JWT — service-to-service HMAC only).

    Envelope:
      { "signal_type": "consensus_match", "user_email_hash": "<sha256 hex>",
        "data": { "match_score": 0.87, "shared_tags": [...], "peer_email_hash": "..." },
        "timestamp": "<iso8601>", "nonce": "<uuid>" }

    Header:
      X-Signal-Signature: HMAC-SHA256(raw_body, SIGNAL_BRIDGE_SECRET) as lowercase hex
    """
    if not _verify_signal_signature():
        return jsonify(error="unauthorized", message="invalid or missing signature"), 401

    data = request.get_json(silent=True) or {}
    signal_type = (data.get("signal_type") or "").strip()
    user_email_hash = (data.get("user_email_hash") or "").strip()
    nonce = (data.get("nonce") or "").strip()

    if not signal_type or not user_email_hash or not nonce:
        return jsonify(
            error="bad_request",
            message="signal_type, user_email_hash, nonce are required",
        ), 400

    db = _get_db()

    # Idempotency gate: at-most-once per (signal_type, user_email_hash, nonce)
    payload_json = _json.dumps(data.get("data"), ensure_ascii=False)
    if not db.record_signal_ingest(signal_type, user_email_hash, nonce, payload_json):
        logger.info("duplicate signal ignored: type=%s nonce=%s", signal_type, nonce)
        return jsonify(status="ok", duplicate=True)

    if signal_type != "consensus_match":
        # 种子期仅处理 consensus_match；未知类型幂等记录后忽略
        logger.info("unknown signal_type ignored: %s", signal_type)
        return jsonify(status="ok", ignored=True, reason="unknown_signal_type")

    # consensus_match: resolve user → 若有进行中 match mission → mission-complete
    user = db.get_user_by_email_hash(user_email_hash)
    if not user:
        logger.info("consensus_match: no user for hash %s", user_email_hash)
        return jsonify(status="ok", matched=False)

    # 确保有 game profile（complete_mission 依赖 profile 行累加 XP）
    if not db.get_game_profile(user["id"]):
        db.upsert_game_profile(user["id"], "", "")

    # 种子期捷径：以 mission_completions 的 UNIQUE(user_id, mission_id) 幂等，
    # 「进行中 match mission」≈「尚未完成过 match mission」；已完成则幂等忽略。
    completion_id, was_new = db.complete_mission(
        user["id"], _MATCH_MISSION_ID, _MATCH_MISSION_XP
    )
    if was_new:
        logger.info(
            "consensus_match: mission %s completed for user %s (+%d XP)",
            _MATCH_MISSION_ID, user["id"], _MATCH_MISSION_XP,
        )
        return jsonify(
            status="ok", matched=True, mission_completed=True,
            mission_id=_MATCH_MISSION_ID, xp_earned=_MATCH_MISSION_XP,
        )

    logger.info(
        "consensus_match: match mission already completed for user %s, ignore",
        user["id"],
    )
    return jsonify(status="ok", matched=True, mission_completed=False)


# ── Signal Bridge 3 outbound (personality_beacon egress) ──

def _parse_personality_detail(detail):
    """Extract (traits, score) from personality_detail if it carries JSON.

    Seed-phase contract: PlanetX has no standalone traits/score dimensions, so
    those are only forwarded when the detail payload already contains them
    (dict with a ``traits`` list and/or numeric ``score``); otherwise ([], None).
    """
    parsed = None
    if detail:
        if isinstance(detail, str):
            try:
                parsed = _json.loads(detail)
            except (ValueError, TypeError):
                parsed = None
        elif isinstance(detail, dict):
            parsed = detail

    traits, score = [], None
    if isinstance(parsed, dict):
        if isinstance(parsed.get("traits"), list):
            traits = parsed["traits"]
        if isinstance(parsed.get("score"), (int, float)):
            score = parsed["score"]
    return traits, score


def _build_personality_beacon_envelope(
    email_hash, personality_type, traits, score, nonce=None, timestamp=None
):
    """Build the personality_beacon envelope per guide §4.4.

    Field order matters for cross-language HMAC agreement — keep the sender
    compact (separators=(",", ":")) to match Node's JSON.stringify output.
    """
    import uuid
    from datetime import datetime, timezone
    return {
        "signal_type": "personality_beacon",
        "user_email_hash": email_hash,
        "data": {
            "personality_type": personality_type,
            "traits": traits,
            "score": score,
        },
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nonce": nonce or str(uuid.uuid4()),
    }


def _send_personality_beacon(db, user_id, personality_type, personality_detail):
    """T3 egress: push a persisted personality result to DemoPPI (chain A)
    and fan-out a frozen signal.envelope.v1 to GFCC (chain B).

    Best-effort — failures only log, never block the profile-sync response.
    Chain A and chain B are independent: either may skip without blocking the other.
    """
    user = db.get_user_by_id(user_id) if user_id else None
    email_hash = (user or {}).get("email_hash") or ""

    if not email_hash:
        logger.info("personality_beacon: user %s has no email_hash, skip", user_id)
        return

    traits, score = _parse_personality_detail(personality_detail)
    envelope = _build_personality_beacon_envelope(
        email_hash, personality_type, traits, score
    )

    url = (current_app.config.get("DEMOPPI_SIGNAL_INGEST_URL") or "").strip()
    secret = current_app.config.get("SIGNAL_BRIDGE_SECRET") or ""

    if not url:
        logger.info("personality_beacon: no DEMOPPI_SIGNAL_INGEST_URL configured, skip chain A")
    elif not secret:
        logger.warning("personality_beacon: SIGNAL_BRIDGE_SECRET not configured, skip chain A")
    else:
        body = _json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "X-Signal-Signature": signature},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            logger.info(
                "personality_beacon: sent for user %s (type=%s)", user_id, personality_type
            )
        except Exception as e:
            logger.warning("personality_beacon: egress failed for user %s: %s", user_id, e)

    gfcc = send_gfcc_personality_beacon(
        email_hash=email_hash,
        personality_type=personality_type,
        traits=traits,
        score=score,
        nonce=envelope["nonce"],
        timestamp=envelope["timestamp"],
        url=(current_app.config.get("GFCC_SIGNAL_INGEST_URL") or "").strip(),
        secret=current_app.config.get("SIGNAL_INGEST_SECRET") or "",
    )
    if gfcc.get("skipped"):
        logger.info("gfcc personality_beacon skip: %s", gfcc.get("reason"))
    elif gfcc.get("ok"):
        logger.info("gfcc personality_beacon sent for user %s", user_id)
    else:
        logger.warning("gfcc personality_beacon failed for user %s: %s", user_id, gfcc)
