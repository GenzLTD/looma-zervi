"""
Poetry search — ChromaDB vector search with timeout; SQLite fallback in routes.
"""
from __future__ import annotations
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger("looma.poetry")


def _search_chroma(query: str, n_results: int) -> list[dict]:
    from src.thomas_core.rag.chroma_client import search_poetry_chroma
    results = search_poetry_chroma(query, n_results=n_results)
    poems = []
    for r in results:
        meta = r.get("metadata", {})
        poems.append({
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "dynasty": meta.get("dynasty", ""),
            "content": r.get("content", ""),
            "theme": meta.get("theme", ""),
        })
    return poems


def _get_search_config():
    mode = os.getenv("POETRY_SEARCH_MODE", "auto").lower()
    timeout = float(os.getenv("POETRY_CHROMA_SEARCH_TIMEOUT", "10"))
    try:
        from flask import current_app
        mode = current_app.config.get("POETRY_SEARCH_MODE", mode)
        timeout = float(current_app.config.get("POETRY_CHROMA_SEARCH_TIMEOUT", timeout))
    except RuntimeError:
        pass
    return mode, timeout


def search_poems(query: str, n_results: int = 3) -> list[dict]:
    """Search poems. Returns [] on timeout/error so routes can SQLite-fallback."""
    mode, timeout = _get_search_config()
    if mode == "sqlite":
        return []

    if mode not in ("chroma", "auto"):
        return []

    try:
        from flask import current_app
        app = current_app._get_current_object()

        def _search_with_context() -> list[dict]:
            with app.app_context():
                return _search_chroma(query, n_results)

        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_search_with_context)
            return fut.result(timeout=timeout) or []
    except FuturesTimeoutError:
        logger.warning(
            "Poetry ChromaDB search timed out after %.1fs (query=%r)",
            timeout, query[:50],
        )
    except Exception as e:
        logger.warning("Poetry ChromaDB search failed: %s", e)
    return []
