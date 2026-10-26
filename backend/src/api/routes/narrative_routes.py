"""
Narrative routes blueprint — Phase 0 feedback collection.
Ownership: Jason

Endpoints:
  POST /v1/narrative/start    - Start a narrative session
  POST /v1/narrative/event    - Log an event during the session
  POST /v1/narrative/end      - Mark session complete/abandoned
  POST /v1/narrative/feedback - Submit convergence-point qualitative feedback
  GET  /v1/narrative/stats    - Admin: aggregated Phase 0 metrics
"""
import logging

from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth, optional_auth

logger = logging.getLogger("looma.narrative")
narrative_bp = Blueprint("narrative", __name__)

VALID_DOMAINS = {"职业域", "诗域", "自我域", "身份域", "信任域", "迷雾域",
                 "career", "poetry", "self", "identity", "trust", "unknown"}
VALID_EVENT_TYPES = {
    "domain_enter", "choice_made", "convergence_reached",
    "share_attempt", "replay",
}


def _get_db():
    return current_app._db


def _user_id():
    """Return authenticated user_id, or None for guests (to satisfy FK constraints)."""
    if g.get("user_tier") == "guest":
        return None
    return g.get("user_id")


def _emit_value_axis_choice(db, user_id, axis, imprint_name, domain, points):
    """Tell GFCC the option axis. Empty URL, guest, or a bad payload skips. Never raises."""
    import uuid

    from src.signal_bridge.gfcc_fanout import send_gfcc_value_axis_choice

    if not user_id:
        return
    try:
        user = db.get_user_by_id(user_id)
        email_hash_value = (user or {}).get("email_hash") or ""
        send_gfcc_value_axis_choice(
            email_hash=email_hash_value,
            axis=axis,
            imprint_name=imprint_name,
            domain=domain,
            points=points,
            nonce=uuid.uuid4().hex,
            url=(current_app.config.get("GFCC_SIGNAL_INGEST_URL") or "").strip(),
            secret=current_app.config.get("SIGNAL_INGEST_SECRET") or "",
        )
    except Exception:
        logger.warning("value_axis_choice emit failed", exc_info=True)


# ── Start session ──

@narrative_bp.route("/start", methods=["POST"])
@optional_auth
def start_session():
    """Start a new narrative session. Guests can play (no auth required)."""
    data = request.get_json() or {}
    domain = data.get("domain", "").strip()

    if not domain:
        return jsonify(error="bad_request", message="domain required"), 400

    if domain not in VALID_DOMAINS:
        return jsonify(error="bad_request", message=f"unknown domain: {domain}"), 400

    user_id = _user_id()

    db = _get_db()
    session_id = db.create_narrative_session(user_id, domain)

    logger.info(f"Narrative session started: {session_id} domain={domain} user={user_id}")
    return jsonify(session_id=session_id, domain=domain), 201


# ── Log event ──

@narrative_bp.route("/event", methods=["POST"])
@optional_auth
def log_event():
    """Log a narrative event within a session."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    event_type = data.get("event_type", "").strip()

    if not session_id or not event_type:
        return jsonify(error="bad_request", message="session_id and event_type required"), 400

    if event_type not in VALID_EVENT_TYPES:
        return jsonify(error="bad_request", message=f"unknown event_type: {event_type}"), 400

    db = _get_db()
    db.log_narrative_event(
        session_id=session_id,
        event_type=event_type,
        domain=data.get("domain"),
        choice=data.get("choice"),
        navigator_line=data.get("navigator_line"),
        metadata=data.get("metadata"),
    )

    return jsonify(ok=True, session_id=session_id, event_type=event_type)


# ── End session ──

@narrative_bp.route("/end", methods=["POST"])
@optional_auth
def end_session():
    """Mark a narrative session as completed or abandoned."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    completed = data.get("completed", False)
    duration_seconds = float(data.get("duration_seconds", 0))

    if not session_id:
        return jsonify(error="bad_request", message="session_id required"), 400

    status = "completed" if completed else "abandoned"

    db = _get_db()
    db.update_narrative_session(session_id, status, duration_seconds)

    # ── Engine cleanup ──
    user_id = _user_id()
    if user_id:
        try:
            from src.agents.domain_engine import get_domain_engine
            from src.agents.navigator_memory import get_navigator_memory

            engine = get_domain_engine(db=db)
            memory = get_navigator_memory(db=db)
            engine.end_session(user_id, session_id)
            memory.on_session_end(user_id)
        except Exception as e:
            logger.warning(f"Engine cleanup failed for session {session_id}: {e}")

    logger.info(f"Narrative session {session_id} → {status} ({duration_seconds}s)")
    return jsonify(ok=True, session_id=session_id, status=status)


# ── Submit feedback ──

@narrative_bp.route("/feedback", methods=["POST"])
@optional_auth
def submit_feedback():
    """Submit convergence-point qualitative feedback.

    Body:
      session_id        (required) - session from /start
      resonated         (required) - bool: did Navigator touch you?
      navigator_quote   (optional) - recalled Navigator line
      would_replay      (optional) - 0=no, 1=maybe, 2=yes
      shared            (optional) - bool: did user share?
      share_channel     (optional) - "wechat"|"moments"|"link"|"other"
      open_feedback     (optional) - free-text qualitative feedback
    """
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()

    if not session_id:
        return jsonify(error="bad_request", message="session_id required"), 400

    resonated = data.get("resonated")
    if resonated is None:
        return jsonify(error="bad_request", message="resonated (bool) required"), 400

    would_replay = data.get("would_replay")
    if would_replay is not None and would_replay not in (0, 1, 2):
        return jsonify(error="bad_request", message="would_replay must be 0, 1, or 2"), 400

    db = _get_db()
    db.submit_narrative_feedback(
        session_id=session_id,
        resonated=bool(resonated),
        navigator_quote=data.get("navigator_quote"),
        would_replay=would_replay,
        shared=bool(data.get("shared", False)),
        share_channel=data.get("share_channel"),
        open_feedback=data.get("open_feedback"),
    )

    logger.info(f"Narrative feedback submitted: {session_id} resonated={resonated}")
    return jsonify(ok=True, session_id=session_id), 201


# ── Stats (admin) ──

@narrative_bp.route("/stats", methods=["GET"])
@require_auth
def get_stats():
    """Get aggregated Phase 0 metrics. Admin only."""
    if g.get("user_role") != "admin":
        return jsonify(error="forbidden", message="admin only"), 403

    db = _get_db()
    stats = db.get_narrative_stats()
    return jsonify(stats)


# =========================================================================
# Engine endpoints (GDD §3 & §7 integration)
# =========================================================================

@narrative_bp.route("/engine/domain-enter", methods=["POST"])
@optional_auth
def engine_domain_enter():
    """Record domain entry and get cross-domain effects.

    Body:
      session_id  (required) - narrative session ID
      domain      (required) - domain being entered
    """
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    domain = data.get("domain", "").strip()

    if not session_id or not domain:
        return jsonify(error="bad_request", message="session_id and domain required"), 400

    if domain not in VALID_DOMAINS:
        return jsonify(error="bad_request", message=f"unknown domain: {domain}"), 400

    user_id = _user_id()
    db = _get_db()

    try:
        from src.agents.domain_engine import get_domain_engine
        engine = get_domain_engine(db=db)

        result = engine.record_domain_enter(user_id, session_id, domain)

        # Also log visit to DB
        if result:
            try:
                db.log_domain_visit(
                    user_id=user_id,
                    session_id=session_id,
                    domain=domain,
                    previous_domain=result.get("previous_domain"),
                    interaction_level=result.get("interaction_level"),
                    echo_triggered=result.get("echo") is not None,
                )
            except Exception:
                pass

        return jsonify(domain_entry=result or {"domain": domain})
    except Exception as e:
        logger.error(f"domain_enter failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/choice", methods=["POST"])
@optional_auth
def engine_record_choice():
    """Record a narrative choice and accumulate value imprint.

    Body:
      session_id  (required)
      domain      (required)
      choice      (required) - description of the choice made
      importance  (optional) - 1.0-5.0, default 1.0
    """
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    domain = data.get("domain", "").strip()
    choice = data.get("choice", "").strip()
    importance = float(data.get("importance", 1.0))

    if not session_id or not domain or not choice:
        return jsonify(error="bad_request",
                       message="session_id, domain, choice required"), 400

    user_id = _user_id()
    db = _get_db()

    try:
        from src.agents.domain_engine import get_domain_engine
        from src.agents.navigator_memory import get_navigator_memory

        engine = get_domain_engine(db=db)
        memory = get_navigator_memory(db=db)

        engine.record_choice(session_id, domain, choice, user_id)
        imprint_result = engine.add_imprint(user_id, domain)

        # Record as Navigator memory
        memory.record_choice(user_id, domain, choice,
                             importance=importance,
                             session_id=session_id)

        # Also log as narrative event
        db.log_narrative_event(
            session_id=session_id,
            event_type="choice_made",
            domain=domain,
            choice=choice,
            metadata={"importance": importance},
        )

        # Check emergent strategies
        strategies = engine.detect_strategies(user_id)
        for s in strategies:
            try:
                db.log_emergent_strategy(user_id, s["strategy"])
            except Exception:
                pass

        return jsonify(
            ok=True,
            imprint=imprint_result,
            strategies_detected=[s["strategy"] for s in strategies] if strategies else [],
        )
    except Exception as e:
        logger.error(f"record_choice failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/state", methods=["GET"])
@optional_auth
def engine_get_state():
    """Get current Navigator engine state for the authenticated user.

    Returns value imprints, domain history, active strategies,
    and convergence status.
    """
    user_id = _user_id()
    session_id = request.args.get("session_id", "").strip()
    db = _get_db()

    try:
        from src.agents.domain_engine import get_domain_engine
        from src.agents.navigator_memory import get_navigator_memory
        from src.agents.convergence import get_convergence

        engine = get_domain_engine(db=db)
        memory = get_navigator_memory(db=db)
        convergence = get_convergence(engine=engine, memory=memory)

        engine_ctx = engine.build_navigator_context(user_id, session_id or "latest")
        memory_stats = memory.get_memory_stats(user_id)

        result = {
            "user_id": user_id,
            "imprints": engine_ctx["imprint"],
            "imprint_total": engine_ctx["imprint_total"],
            "dominant_axis": engine_ctx["dominant_axis"],
            "is_balanced": engine_ctx["is_balanced"],
            "is_extreme": engine_ctx["is_extreme"],
            "estimated_act": engine_ctx["estimated_act"],
            "visited_domains": engine_ctx["visited_domains"],
            "domain_count": engine_ctx["domain_count"],
            "echo_chain_length": engine_ctx["echo_chain_length"],
            "active_strategies": engine_ctx["active_strategies"],
            "memory": memory_stats,
        }

        if session_id:
            result["convergence"] = convergence.get_convergence_stats(user_id, session_id)

        return jsonify(result)
    except Exception as e:
        logger.error(f"get_state failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/matrix", methods=["GET"])
def engine_get_matrix():
    """Get the 6×6 domain interaction matrix (public, for reference)."""
    matrix: dict[str, dict[str, dict]] = {}
    for (src, tgt), (level, desc) in _load_matrix().items():
        if src not in matrix:
            matrix[src] = {}
        matrix[src][tgt] = {"level": level.value, "description": desc}
    return jsonify(matrix=matrix, domains=VALID_DOMAINS)


def _load_matrix():
    """Lazy import the interaction matrix."""
    from src.agents.domain_engine import INTERACTION_MATRIX
    return INTERACTION_MATRIX


# =========================================================================
# Act 1 State Machine endpoints (GDD §5.1 integration)
# =========================================================================

@narrative_bp.route("/engine/act1/init", methods=["POST"])
@optional_auth
def act1_init():
    """Initialize an Act 1 session for a given domain.

    Body:
      session_id  (required) - narrative session ID
      domain      (required) - domain to enter (职业域/身份域/诗域/信任域/自我域/迷雾域)
    """
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    domain = data.get("domain", "").strip()

    if not session_id or not domain:
        return jsonify(error="bad_request", message="session_id and domain required"), 400

    if domain not in VALID_DOMAINS:
        return jsonify(error="bad_request", message=f"unknown domain: {domain}"), 400

    user_id = _user_id()

    try:
        from src.agents.act1_state_machine import get_act1
        db = _get_db()
        act1 = get_act1(db=db)
        act1.init_session(session_id, user_id)
        state = act1.select_domain(session_id, domain)

        # Also log domain_enter on the engine side
        db = _get_db()
        try:
            from src.agents.domain_engine import get_domain_engine
            engine = get_domain_engine(db=db)
            engine.record_domain_enter(user_id, session_id, domain)
            db.log_domain_visit(
                user_id=user_id, session_id=session_id, domain=domain,
                previous_domain=None, interaction_level=None, echo_triggered=False,
            )
        except Exception:
            pass

        return jsonify(state.to_dict()), 201
    except Exception as e:
        logger.error(f"act1_init failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/act1/state", methods=["GET"])
@optional_auth
def act1_get_state():
    """Get current Act 1 state for a session.

    Query: session_id (required)
    """
    session_id = request.args.get("session_id", "").strip()
    if not session_id:
        return jsonify(error="bad_request", message="session_id required"), 400

    try:
        from src.agents.act1_state_machine import get_act1
        db = _get_db()
        act1 = get_act1(db=db)
        state = act1.get_state(session_id)
        if state is None:
            return jsonify(error="not_found", message="session not initialized"), 404
        return jsonify(state.to_dict())
    except Exception as e:
        logger.error(f"act1_get_state failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/act1/advance", methods=["POST"])
@optional_auth
def act1_advance():
    """Advance to the next step in the Act 1 narrative.

    Body:
      session_id  (required)
    """
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()

    if not session_id:
        return jsonify(error="bad_request", message="session_id required"), 400

    try:
        from src.agents.act1_state_machine import get_act1
        db = _get_db()
        act1 = get_act1(db=db)
        result = act1.advance(session_id)

        if result.get("error"):
            return jsonify(error="state_error", message=result["error"], state=result), 400

        # Optionally log as narrative event
        try:
            db.log_narrative_event(
                session_id=session_id,
                event_type="domain_enter" if result["step"] <= 2 else "choice_made",
                domain=result.get("domain"),
                choice=result.get("imprint_name"),
                metadata={"act1_step": result["step"], "label": result.get("label")},
            )
        except Exception:
            pass

        return jsonify(result)
    except Exception as e:
        logger.error(f"act1_advance failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/act1/choice", methods=["POST"])
@optional_auth
def act1_make_choice():
    """Make a choice at Act 1 step 3 (domain) or step 7 (cross-domain).

    Body:
      session_id     (required)
      choice_index   (required) - 0, 1, or 2
    """
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    choice_index = int(data.get("choice_index", -1))

    if not session_id or choice_index < 0:
        return jsonify(error="bad_request", message="session_id and choice_index required"), 400

    user_id = _user_id()
    db = _get_db()

    try:
        from src.agents.act1_state_machine import get_act1
        act1 = get_act1(db=db)
        result = act1.make_choice(session_id, choice_index)

        if result.get("error"):
            return jsonify(error="state_error", message=result["error"]), 400

        state = act1.get_state(session_id)
        is_cross = result.get("is_cross_choice", False)

        # Record imprint via engine
        if state and state.domain:
            try:
                from src.agents.domain_engine import get_domain_engine
                from src.agents.navigator_memory import get_navigator_memory

                engine = get_domain_engine(db=db)
                memory = get_navigator_memory(db=db)

                imprint_axis = result.get("imprint_axis") or ""
                imprint_points = int(result.get("imprint_points") or 0)
                target_domain = "诗域" if is_cross else state.domain
                imprint_name = result.get("imprint_name", "")

                engine.record_choice(session_id, target_domain, imprint_name, user_id)
                engine.add_imprint(
                    user_id, target_domain, imprint_points, axis=imprint_axis,
                )
                _emit_value_axis_choice(
                    db, user_id, imprint_axis, imprint_name, target_domain,
                    imprint_points,
                )

                memory.record_choice(
                    user_id=user_id,
                    domain=target_domain,
                    choice=result.get("imprint_name", ""),
                    importance=float(imprint_points) / 3.0,
                    session_id=session_id,
                )
            except Exception:
                pass

        # Log choice as narrative event
        try:
            db.log_narrative_event(
                session_id=session_id,
                event_type="cross_domain_choice" if is_cross else "choice_made",
                domain="诗域" if is_cross else (state.domain if state else ""),
                choice=result.get("imprint_name", ""),
                metadata={
                    "choice_index": choice_index,
                    "imprint_axis": result.get("imprint_axis"),
                    "is_cross_choice": is_cross,
                },
            )
        except Exception:
            pass

        # Auto-advance
        advance_result = act1.advance(session_id)
        result["step"] = advance_result.get("step", 4)
        result["consequence"] = advance_result.get("narrative")

        return jsonify(result)
    except Exception as e:
        logger.error(f"act1_make_choice failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/act1/reset", methods=["POST"])
@optional_auth
def act1_reset():
    """Reset current Act 1 path (keep domain, reset steps).

    Body:
      session_id  (required)
      hard        (optional) - if true, clear domain too
    """
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    hard = data.get("hard", False)

    if not session_id:
        return jsonify(error="bad_request", message="session_id required"), 400

    try:
        from src.agents.act1_state_machine import get_act1
        db = _get_db()
        act1 = get_act1(db=db)
        if hard:
            act1.hard_reset(session_id)
        else:
            act1.reset(session_id)
        return jsonify(ok=True, session_id=session_id, hard=hard)
    except Exception as e:
        logger.error(f"act1_reset failed: {e}", exc_info=True)
        return jsonify(error="engine_error", message=str(e)), 500


@narrative_bp.route("/engine/act1/content", methods=["GET"])
def act1_get_content():
    """Get Act 1 narrative content library (domains, steps, choices).
    Used by frontend to bootstrap the UI without hardcoding narrative text.

    Query:
      domain (optional) - filter to single domain content
    """
    from src.agents.narrative_content import (
        DOMAIN_CONTENT, ACT1_STEPS, NAVIGATOR_LINES, get_convergence_comparison, VERDICT_TEXT,
    )

    domain_filter = request.args.get("domain", "").strip()

    if domain_filter:
        from src.agents.narrative_content import get_domain
        d = get_domain(domain_filter)
        if d is None:
            return jsonify(error="bad_request", message=f"unknown domain: {domain_filter}"), 400
        return jsonify(domain=d, steps=ACT1_STEPS)

    return jsonify(
        domains={
            name: {
                "icon": data["icon"],
                "en": data["en"],
                "color": data["color"],
                "emotion_arc": data["emotion_arc"],
                "encounter_summary": data["encounter"][:80] + "…",
                "choice_count": len(data["choices"]),
            }
            for name, data in DOMAIN_CONTENT.items()
        },
        steps=ACT1_STEPS,
        navigator_lines={
            key: {"line": val["line"][:60] + "…", "confidence": val["confidence"]}
            for key, val in NAVIGATOR_LINES.items()
        },
        convergence_comparison=get_convergence_comparison(),
        verdict=VERDICT_TEXT[:200] + "…",
    )
