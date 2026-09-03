"""
Poetry routes blueprint — browse, search, discover Chinese classical poems.
Ownership: Jason

Endpoints:
  GET  /v1/poetry/search   - Semantic search via ChromaDB vector
  GET  /v1/poetry/browse   - Filter + paginate (dynasty/author/theme/keyword)
  GET  /v1/poetry/:id      - Get single poem full content
  GET  /v1/poetry/random   - Discovery: random poems
  GET  /v1/poetry/stats    - Collection stats (total, dynasty/theme distribution)
  GET  /v1/poetry/authors  - Distinct authors list with counts (pagination)
  GET  /v1/poetry/challenge/current - This week's Xin-Da-Ya challenge
  POST /v1/poetry/challenge/entries - Submit / update English translation
"""
import logging
import re
from flask import Blueprint, request, jsonify, g, current_app

from src.api.auth.decorators import optional_auth, require_auth

logger = logging.getLogger("looma.poetry")

poetry_bp = Blueprint("poetry", __name__)

_MIN_TRANSLATION_LEN = 8
_MAX_TRANSLATION_LEN = 2000
_MAX_NOTE_LEN = 200


def _get_db():
    return current_app._db


def _serialize_entry(entry: dict | None) -> dict | None:
    if not entry:
        return None
    return {
        "id": entry["id"],
        "round_id": entry["round_id"],
        "translation": entry["translation"],
        "note": entry.get("note") or "",
        "license_accepted": bool(entry.get("license_accepted")),
        "vote_count": entry.get("vote_count", 0),
        "created_at": entry.get("created_at"),
        "updated_at": entry.get("updated_at"),
    }


# ── Xin-Da-Ya challenge (overseas MVP) ──

@poetry_bp.route("/challenge/current", methods=["GET"])
@optional_auth
def challenge_current():
    """Return this week's translation challenge + poem + caller's entry (if any)."""
    db = _get_db()
    round_row = db.ensure_current_challenge_round()
    if not round_row:
        return jsonify(
            error="library_empty",
            message="Poetry library has no poems yet; cannot open a challenge round.",
            round=None,
            poem=None,
            my_entry=None,
        ), 503

    poem = db.get_poem_by_id(round_row["poem_id"])
    if not poem:
        return jsonify(
            error="poem_missing",
            message="Challenge poem not found",
            round=None,
            poem=None,
            my_entry=None,
        ), 404

    my_entry = None
    user_id = g.get("user_id")
    if user_id and not str(user_id).startswith("guest"):
        my_entry = _serialize_entry(
            db.get_challenge_entry(round_row["id"], user_id)
        )

    return jsonify(
        round={
            "id": round_row["id"],
            "week_key": round_row["week_key"],
            "title": round_row.get("title") or "",
            "status": round_row.get("status") or "open",
            "starts_at": round_row["starts_at"],
            "ends_at": round_row["ends_at"],
            "poem_id": round_row["poem_id"],
        },
        poem={
            "id": poem["id"],
            "title": poem.get("title") or "",
            "author": poem.get("author") or "",
            "dynasty": poem.get("dynasty") or "",
            "theme": poem.get("theme") or "",
            "content": poem.get("content") or "",
        },
        my_entry=my_entry,
    )


@poetry_bp.route("/challenge/entries", methods=["POST"])
@require_auth
def challenge_submit_entry():
    """Submit or update the caller's English translation for the current open round."""
    data = request.get_json(silent=True) or {}
    translation = (data.get("translation") or "").strip()
    note = (data.get("note") or "").strip()
    license_accepted = bool(data.get("license_accepted"))
    round_id = data.get("round_id")

    if not license_accepted:
        return jsonify(
            error="license_required",
            message="You must accept the display license to submit.",
        ), 400

    if len(translation) < _MIN_TRANSLATION_LEN:
        return jsonify(
            error="translation_too_short",
            message=f"Translation must be at least {_MIN_TRANSLATION_LEN} characters.",
        ), 400

    if len(translation) > _MAX_TRANSLATION_LEN:
        return jsonify(
            error="translation_too_long",
            message=f"Translation must be at most {_MAX_TRANSLATION_LEN} characters.",
        ), 400

    if len(note) > _MAX_NOTE_LEN:
        return jsonify(
            error="note_too_long",
            message=f"Note must be at most {_MAX_NOTE_LEN} characters.",
        ), 400

    # Reject submissions with no Latin letters (likely not English)
    if not re.search(r"[A-Za-z]", translation):
        return jsonify(
            error="translation_not_english",
            message="Please submit an English translation.",
        ), 400

    db = _get_db()
    round_row = db.ensure_current_challenge_round()
    if not round_row:
        return jsonify(
            error="library_empty",
            message="Poetry library is empty; challenge unavailable.",
        ), 503

    if round_row.get("status") != "open":
        return jsonify(error="round_closed", message="This week's challenge is closed."), 403

    if round_id is not None and int(round_id) != int(round_row["id"]):
        return jsonify(
            error="round_mismatch",
            message="round_id does not match the current open challenge.",
        ), 409

    entry = db.upsert_challenge_entry(
        round_id=round_row["id"],
        user_id=g.user_id,
        translation=translation,
        note=note,
        license_accepted=license_accepted,
    )
    return jsonify(entry=_serialize_entry(entry), round_id=round_row["id"]), 200


# ── Semantic search (ChromaDB) ──

@poetry_bp.route("/search", methods=["GET"])
@optional_auth
def search_poems():
    """Search poems.

    Query param: q (required), n (optional, default 3).

    Strategy (default "auto"): literal keyword match first (after s2t
    normalization, since the corpus is Traditional), then fall back to
    ChromaDB vector search. The prebuilt poetry vector index uses the default
    all-MiniLM-L6-v2 embedder, which is weak for Chinese, so the literal path
    gives far better recall for short-phrase queries.
    """
    query = request.args.get("q", "").strip()
    n_results = int(request.args.get("n", 3))

    if not query:
        return jsonify(error="bad_request", message="q parameter required"), 400

    mode = current_app.config.get("POETRY_SEARCH_MODE", "auto")

    # Normalize Simplified -> Traditional so literal match aligns with corpus.
    from src.utils.textnorm import to_traditional
    normalized = to_traditional(query)

    poems: list[dict] = []
    search_backend: str | None = None

    # 1) Literal keyword match (s2t-normalized) — best recall for short phrases.
    if mode in ("auto", "sqlite"):
        db = _get_db()
        result = db.get_poems(keyword=normalized, per_page=n_results)
        poems = [
            {
                "title": p["title"],
                "author": p["author"],
                "dynasty": p["dynasty"],
                "content": p.get("content_preview", ""),
                "theme": p["theme"],
            }
            for p in result["items"]
        ]
        search_backend = "sqlite"

    # 2) Fall back to ChromaDB vector search when literal match yields nothing.
    if not poems and mode in ("auto", "chroma"):
        try:
            from src.agents.poetry_search import search_poems as _search_poems
            poems = _search_poems(query, n_results=n_results)
            search_backend = "chroma"
        except Exception as e:
            logger.warning(f"Poetry vector search failed: {e}")

    return jsonify(
        results=poems, query=query, count=len(poems), search_backend=search_backend
    )


# ── Browse / filter (SQLite) ──

@poetry_bp.route("/browse", methods=["GET"])
@optional_auth
def browse_poems():
    """Browse poems with filtering and pagination.
    Query params: dynasty, author, theme, keyword, page (default 1), per_page (default 20).
    """
    dynasty = request.args.get("dynasty")
    author = request.args.get("author")
    theme = request.args.get("theme")
    keyword = request.args.get("keyword")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    # Cap per_page to avoid huge responses
    per_page = min(per_page, 50)

    db = _get_db()
    result = db.get_poems(
        dynasty=dynasty, author=author, theme=theme,
        keyword=keyword, page=page, per_page=per_page
    )

    return jsonify(result)


# ── Single poem ──

@poetry_bp.route("/<int:poem_id>", methods=["GET"])
@optional_auth
def get_poem(poem_id):
    """Get a single poem's full content by id."""
    db = _get_db()
    poem = db.get_poem_by_id(poem_id)

    if not poem:
        return jsonify(error="not_found", message=f"Poem {poem_id} not found"), 404

    return jsonify(poem)


# ── Random discovery ──

@poetry_bp.route("/random", methods=["GET"])
@optional_auth
def random_poems():
    """Discovery mode: get random poems.
    Query param: count (default 3).
    """
    count = int(request.args.get("count", 3))
    count = min(count, 10)  # cap at 10

    db = _get_db()
    poems = db.get_random_poems(count)

    return jsonify(results=poems, count=len(poems))


# ── Collection stats ──

@poetry_bp.route("/stats", methods=["GET"])
@optional_auth
def poetry_stats():
    """Get poetry collection statistics."""
    db = _get_db()
    stats = db.get_poetry_stats()
    return jsonify(stats)


# ── Authors / poets ──

@poetry_bp.route("/authors", methods=["GET"])
@optional_auth
def list_authors():
    """List distinct authors with counts, sorted by poem count desc.

    Query params: dynasty (optional filter), page (default 1), per_page (default 24, max 100).
    """
    dynasty = request.args.get("dynasty")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 24))
    per_page = min(per_page, 100)

    db = _get_db()
    result = db.get_authors(dynasty=dynasty, page=page, per_page=per_page)
    return jsonify(result)