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
"""
import logging
from flask import Blueprint, request, jsonify, current_app

from src.api.auth.decorators import optional_auth

logger = logging.getLogger("looma.poetry")

poetry_bp = Blueprint("poetry", __name__)


def _get_db():
    return current_app._db


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