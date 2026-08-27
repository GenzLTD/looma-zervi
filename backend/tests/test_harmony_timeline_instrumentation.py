"""Harmony-facing contract + timeline instrumentation smoke tests (no Huawei network)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.timeline.constants import EVENT_KIND_ALLOW_DUPLICATE, EVENT_KIND_PHASE1
from src.timeline.events import (
    record_interaction_log,
    record_learning_activity,
    record_match_scan,
    record_mission_completed,
)


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def test_harmony_contract_file_exists():
    path = CONTRACTS / "harmony.v1.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["auth"]["login"]["path"] == "/v1/auth/huawei"
    assert "interaction_log" in json.dumps(data["timeline_auto_writers"])


def test_timeline_contract_includes_mission_and_gdpr():
    data = json.loads((CONTRACTS / "timeline.v1.json").read_text(encoding="utf-8"))
    required = data["enums"]["event_kind"]["phase1_required"]
    assert "mission_completed" in required
    assert "learning_activity" in required
    paths = {e["path"] for e in data["api"]["endpoints"]}
    assert "/v1/timeline/export" in paths
    assert "/v1/timeline/me" in paths


def test_identity_contract_includes_huawei():
    data = json.loads((CONTRACTS / "identity.v1.json").read_text(encoding="utf-8"))
    assert "huawei" in data["linked_account_provider_enum"]
    paths = {e["path"] for e in data["endpoints"]["implemented"]}
    assert "/v1/auth/huawei" in paths


def test_phase1_kinds_cover_harmony_writers():
    for kind in (
        "interaction_log",
        "mission_completed",
        "learning_activity",
        "match_scan",
        "resume_ingest",
    ):
        assert kind in EVENT_KIND_PHASE1
    assert "interaction_log" in EVENT_KIND_ALLOW_DUPLICATE
    assert "match_scan" in EVENT_KIND_ALLOW_DUPLICATE


def test_record_writers_do_not_raise_without_db(monkeypatch):
    """record_* must swallow DB failures (best-effort)."""

    class Boom:
        def insert_timeline_event(self, *a, **k):
            raise RuntimeError("db down")

    db = Boom()
    assert record_interaction_log(db, "u1", query="hello", intent="chat") is None
    assert record_mission_completed(db, "u1", mission_id="team", xp_reward=10) is None
    assert record_learning_activity(db, "u1", source_ref="sess1") is None
    assert record_match_scan(db, "u1", report_id="r1", total_jobs=3) is None


def test_huawei_auth_uses_correct_identity_kwargs():
    """Static guard: auth_routes must call get_or_create_user_by_identity with name=/metadata_json=."""
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "api"
        / "routes"
        / "auth_routes.py"
    ).read_text(encoding="utf-8")
    # Regression: previously passed invalid extra_data= kwarg → TypeError at runtime
    assert "extra_data=" not in src.split("def huawei_login")[1].split("def ")[0]
    assert 'provider="huawei"' in src
    assert "metadata_json=" in src.split("def huawei_login")[1].split("def ")[0]
