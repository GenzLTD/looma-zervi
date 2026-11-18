"""RAG Ask 生成出境分轨：隐私轨零云调用 / 公开可云 / local_only / off 回滚。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.config import (
    _refresh_config,
    llm_policy_baseline,
    llm_policy_violations,
    rag_egress_for_collection,
    resolve_llm_provider_order,
    resolve_rag_cloud_allowed_collections,
    resolve_rag_privacy_mode,
)


@pytest.fixture(autouse=True)
def _restore_config():
    yield
    _refresh_config()


# ── config helpers ──────────────────────────────────────────────────────────


def test_rag_privacy_mode_defaults_dual(monkeypatch):
    monkeypatch.delenv("RAG_PRIVACY_MODE", raising=False)
    assert resolve_rag_privacy_mode() == "dual"


def test_rag_privacy_mode_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("RAG_PRIVACY_MODE", "bogus")
    assert resolve_rag_privacy_mode() == "dual"


def test_rag_cloud_allowed_default_poetry(monkeypatch):
    monkeypatch.delenv("RAG_CLOUD_ALLOWED_COLLECTIONS", raising=False)
    assert resolve_rag_cloud_allowed_collections() == ["poetry_full"]


def test_rag_egress_dual_private_vs_public(monkeypatch):
    monkeypatch.setenv("RAG_PRIVACY_MODE", "dual")
    monkeypatch.setenv("RAG_CLOUD_ALLOWED_COLLECTIONS", "poetry_full")
    assert rag_egress_for_collection("looma_knowledge") == "local_only"
    assert rag_egress_for_collection("poetry_full") == "cloud_ok"


def test_rag_egress_local_only_mode(monkeypatch):
    monkeypatch.setenv("RAG_PRIVACY_MODE", "local_only")
    monkeypatch.setenv("RAG_CLOUD_ALLOWED_COLLECTIONS", "poetry_full")
    assert rag_egress_for_collection("poetry_full") == "local_only"
    assert rag_egress_for_collection("looma_knowledge") == "local_only"


def test_rag_egress_off_mode(monkeypatch):
    monkeypatch.setenv("RAG_PRIVACY_MODE", "off")
    assert rag_egress_for_collection("looma_knowledge") == "cloud_ok"


def test_llm_policy_baseline_and_violations(monkeypatch):
    monkeypatch.setenv("DEPLOY_REGION", "CN")
    assert llm_policy_baseline() == "deepseek,ollama"
    assert llm_policy_violations("openai,ollama") == ["openai"]
    monkeypatch.delenv("LLM_PROVIDER_ORDER", raising=False)
    assert resolve_llm_provider_order() == "deepseek,ollama"


def test_deepseek_rag_answer_hard_guard():
    from src.thomas_core.llm.deepseek_client import rag_answer

    with pytest.raises(RuntimeError, match="disabled"):
        rag_answer("q", ["chunk"])


# ── _call_llm allowed_providers ─────────────────────────────────────────────


def test_call_llm_local_only_never_hits_deepseek(app, monkeypatch):
    """Privacy gate: allowed_providers=(ollama,) must not POST to DeepSeek."""
    from src.agents import central_brain as cb

    calls: list[str] = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if "/api/generate" in url:
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"response": "local-ok"}
            return resp
        raise AssertionError(f"unexpected cloud call: {url}")

    monkeypatch.setattr(cb.requests, "post", fake_post)
    app.config["LLM_PROVIDER_ORDER"] = "deepseek,ollama"
    app.config["DEEPSEEK_API_KEY"] = "sk-test-not-skip"
    app.config["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com/v1"
    app.config["DEEPSEEK_MODEL"] = "deepseek-chat"
    app.config["OLLAMA_HOST"] = "http://127.0.0.1:11434"
    app.config["OLLAMA_MODEL"] = "qwen2.5:7b"

    with app.app_context():
        meta: dict = {}
        text = cb._call_llm(
            "prompt with private corpus",
            allowed_providers=("ollama",),
            meta=meta,
        )

    assert text == "local-ok"
    assert meta.get("provider") == "ollama"
    assert all("deepseek" not in u for u in calls)
    assert any("/api/generate" in u for u in calls)


def test_call_llm_local_only_ollama_down_returns_none(app, monkeypatch):
    from src.agents import central_brain as cb

    def fake_post(url, **kwargs):
        if "deepseek" in url or "openai" in url:
            raise AssertionError(f"cloud must not be called: {url}")
        raise ConnectionError("ollama down")

    monkeypatch.setattr(cb.requests, "post", fake_post)
    app.config["LLM_PROVIDER_ORDER"] = "deepseek,ollama"
    app.config["DEEPSEEK_API_KEY"] = "sk-test-not-skip"
    app.config["OLLAMA_HOST"] = "http://127.0.0.1:11434"

    with app.app_context():
        text = cb._call_llm("x", allowed_providers=("ollama",))
    assert text is None


# ── dispatch RAG egress ─────────────────────────────────────────────────────


def _rag_hit():
    return [{"id": "c1", "content": "SECRET_CORPUS_CHUNK", "score": 0.9, "metadata": {}}]


def test_dispatch_rag_private_refuse_when_ollama_down(app, monkeypatch):
    """dual + looma_knowledge + ollama fail → rag_local_required, zero deepseek."""
    from src.agents import central_brain as cb

    monkeypatch.setenv("RAG_PRIVACY_MODE", "dual")
    monkeypatch.setenv("RAG_CLOUD_ALLOWED_COLLECTIONS", "poetry_full")
    _refresh_config()
    app.config["RAG_PRIVACY_MODE"] = "dual"
    app.config["RAG_CLOUD_ALLOWED_COLLECTIONS"] = "poetry_full"
    app.config["CHROMA_COLLECTION"] = "looma_knowledge"
    app.config["LLM_PROVIDER_ORDER"] = "deepseek,ollama"
    app.config["DEEPSEEK_API_KEY"] = "sk-test-not-skip"
    app.config["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com/v1"
    app.config["OLLAMA_HOST"] = "http://127.0.0.1:11434"

    monkeypatch.setattr(
        "src.thomas_core.rag.chroma_client.search_chroma",
        lambda *a, **k: _rag_hit(),
    )

    cloud_hits: list[str] = []

    def fake_post(url, **kwargs):
        cloud_hits.append(url)
        if "deepseek" in url or "openai" in url:
            raise AssertionError(f"must not call cloud: {url}")
        raise ConnectionError("ollama down")

    monkeypatch.setattr(cb.requests, "post", fake_post)

    with app.app_context():
        out = cb.dispatch("rag", "介绍一下知识库")

    assert out.get("error") == "rag_local_required"
    assert out.get("egress") == "local_only"
    assert "SECRET" not in (out.get("answer") or "")
    assert all(not (s.get("chunk_text") or "") for s in out.get("_sources") or [])
    assert not any("deepseek" in u for u in cloud_hits)


def test_dispatch_rag_private_uses_ollama_only(app, monkeypatch):
    from src.agents import central_brain as cb

    monkeypatch.setenv("RAG_PRIVACY_MODE", "dual")
    monkeypatch.setenv("RAG_CLOUD_ALLOWED_COLLECTIONS", "poetry_full")
    _refresh_config()
    app.config["RAG_PRIVACY_MODE"] = "dual"
    app.config["RAG_CLOUD_ALLOWED_COLLECTIONS"] = "poetry_full"
    app.config["CHROMA_COLLECTION"] = "looma_knowledge"
    app.config["LLM_PROVIDER_ORDER"] = "deepseek,ollama"
    app.config["DEEPSEEK_API_KEY"] = "sk-test-not-skip"
    app.config["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com/v1"
    app.config["OLLAMA_HOST"] = "http://127.0.0.1:11434"
    app.config["OLLAMA_MODEL"] = "qwen2.5:7b"

    monkeypatch.setattr(
        "src.thomas_core.rag.chroma_client.search_chroma",
        lambda *a, **k: _rag_hit(),
    )

    def fake_post(url, **kwargs):
        if "deepseek" in url:
            raise AssertionError("deepseek forbidden on private track")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"response": "from-ollama"}
        return resp

    monkeypatch.setattr(cb.requests, "post", fake_post)

    with app.app_context():
        out = cb.dispatch("rag", "知识库是什么")

    assert out.get("error") is None
    assert out.get("egress") == "local_only"
    assert out.get("llm_provider") == "ollama"
    assert out.get("answer") == "from-ollama"


def test_dispatch_rag_public_collection_may_use_deepseek(app, monkeypatch):
    from src.agents import central_brain as cb

    monkeypatch.setenv("RAG_PRIVACY_MODE", "dual")
    monkeypatch.setenv("RAG_CLOUD_ALLOWED_COLLECTIONS", "looma_knowledge")
    _refresh_config()
    app.config["RAG_PRIVACY_MODE"] = "dual"
    app.config["RAG_CLOUD_ALLOWED_COLLECTIONS"] = "looma_knowledge"
    app.config["CHROMA_COLLECTION"] = "looma_knowledge"
    app.config["LLM_PROVIDER_ORDER"] = "deepseek,ollama"
    app.config["DEEPSEEK_API_KEY"] = "sk-test-not-skip"
    app.config["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com/v1"
    app.config["DEEPSEEK_MODEL"] = "deepseek-chat"

    monkeypatch.setattr(
        "src.thomas_core.rag.chroma_client.search_chroma",
        lambda *a, **k: _rag_hit(),
    )

    def fake_post(url, **kwargs):
        if "deepseek.com" not in url:
            raise AssertionError(f"expected deepseek first, got {url}")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "choices": [{"message": {"content": "from-deepseek"}}],
            "usage": {},
        }
        return resp

    monkeypatch.setattr(cb.requests, "post", fake_post)

    with app.app_context():
        out = cb.dispatch("rag", "介绍一下")

    assert out.get("egress") == "cloud_ok"
    assert out.get("llm_provider") == "deepseek"
    assert out.get("answer") == "from-deepseek"


def test_dispatch_poetry_local_only_mode_blocks_cloud(app, monkeypatch):
    from src.agents import central_brain as cb

    monkeypatch.setenv("RAG_PRIVACY_MODE", "local_only")
    monkeypatch.setenv("RAG_CLOUD_ALLOWED_COLLECTIONS", "poetry_full")
    _refresh_config()
    app.config["RAG_PRIVACY_MODE"] = "local_only"
    app.config["RAG_CLOUD_ALLOWED_COLLECTIONS"] = "poetry_full"
    app.config["LLM_PROVIDER_ORDER"] = "deepseek,ollama"
    app.config["DEEPSEEK_API_KEY"] = "sk-test-not-skip"
    app.config["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com/v1"
    app.config["OLLAMA_HOST"] = "http://127.0.0.1:11434"

    poem = {
        "title": "静夜思",
        "author": "李白",
        "dynasty": "唐",
        "content": "床前明月光",
    }
    monkeypatch.setattr(
        "src.agents.poetry_search.search_poems",
        lambda *a, **k: [poem],
    )

    def fake_post(url, **kwargs):
        if "deepseek" in url:
            raise AssertionError("poetry local_only must not call deepseek")
        raise ConnectionError("ollama down")

    monkeypatch.setattr(cb.requests, "post", fake_post)

    with app.app_context():
        out = cb.dispatch("poetry", "推荐一首思乡诗")

    assert out.get("error") == "rag_local_required"
    assert out.get("egress") == "local_only"
