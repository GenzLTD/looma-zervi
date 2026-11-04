"""Lock 4: dual-track /health IDs — tip vs join_pin, no cross-track impersonation."""
from __future__ import annotations

import pytest

from src.app import _dual_track_health_ids, _git_commit


@pytest.fixture(autouse=True)
def _clear_git_commit_cache():
    _git_commit.cache_clear()
    yield
    _git_commit.cache_clear()


def test_looma_track_reports_deploy_tip(monkeypatch):
    monkeypatch.delenv("DEPLOY_REGION", raising=False)
    monkeypatch.delenv("LOOMA_SHA", raising=False)
    monkeypatch.delenv("LOOMA_JOIN_SHA", raising=False)
    monkeypatch.delenv("VULTR_TAG", raising=False)
    monkeypatch.delenv("STACK_TAG", raising=False)
    monkeypatch.delenv("STACK_SHA", raising=False)
    monkeypatch.setenv("GIT_COMMIT", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    ids = _dual_track_health_ids()
    assert ids["deploy_track"] == "looma"
    assert ids["looma_sha"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert ids["looma_sha_kind"] == "deploy_tip"
    assert ids["vultr_tag"] is None
    assert ids["stack_sha"] is None


def test_looma_track_ignores_stray_stack_env(monkeypatch):
    """CN must not surface stack markers even if .env was polluted with STACK_SHA."""
    monkeypatch.delenv("DEPLOY_REGION", raising=False)
    monkeypatch.delenv("VULTR_TAG", raising=False)
    monkeypatch.delenv("STACK_TAG", raising=False)
    monkeypatch.setenv("GIT_COMMIT", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    monkeypatch.setenv("STACK_SHA", "should-not-leak-on-looma-track")
    monkeypatch.setenv("LOOMA_SHA", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    ids = _dual_track_health_ids()
    assert ids["deploy_track"] == "looma"
    assert ids["stack_sha"] is None
    assert ids["vultr_tag"] is None


def test_vultr_track_join_pin_not_tip(monkeypatch):
    monkeypatch.setenv("DEPLOY_REGION", "SG")
    monkeypatch.setenv("GIT_COMMIT", "cccccccccccccccccccccccccccccccccccccccc")
    monkeypatch.setenv("STACK_SHA", "cccccccccccccccccccccccccccccccccccccccc")
    monkeypatch.setenv("VULTR_TAG", "stack-v0.1.14")
    monkeypatch.setenv("LOOMA_SHA", "dddddddddddddddddddddddddddddddddddddddd")

    ids = _dual_track_health_ids()
    assert ids["deploy_track"] == "vultr"
    assert ids["stack_sha"] == "cccccccccccccccccccccccccccccccccccccccc"
    assert ids["vultr_tag"] == "stack-v0.1.14"
    assert ids["looma_sha"] == "dddddddddddddddddddddddddddddddddddddddd"
    assert ids["looma_sha_kind"] == "join_pin"
    # join pin must not equal a silent fallback to stack tip when PIN missing
    monkeypatch.delenv("LOOMA_SHA", raising=False)
    monkeypatch.delenv("LOOMA_JOIN_SHA", raising=False)
    ids2 = _dual_track_health_ids()
    assert ids2["looma_sha"] is None
    assert ids2["looma_sha_kind"] is None
    assert ids2["stack_sha"] == "cccccccccccccccccccccccccccccccccccccccc"