"""
Signal Bridge 2/3 inbound (T1) tests — HMAC + idempotency + consensus_match → mission-complete.
Run: pytest tests/test_signal_ingest.py -v
"""
import hashlib as _hashlib
import hmac as _hmac
import json as _json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SIGNAL_SECRET = "test-signal-bridge-secret-2026"


def _sign(body: bytes, secret: str = SIGNAL_SECRET) -> str:
    return _hmac.new(secret.encode("utf-8"), body, _hashlib.sha256).hexdigest()


def _envelope(signal_type, user_email_hash, nonce, data=None):
    return {
        "signal_type": signal_type,
        "user_email_hash": user_email_hash,
        "nonce": nonce,
        "data": data or {},
    }


def _post(client, body: dict):
    """POST signal-ingest with a valid HMAC signature over the exact body bytes."""
    raw = _json.dumps(body, ensure_ascii=False).encode("utf-8")
    return client.post(
        "/v1/game/signal-ingest",
        data=raw,
        content_type="application/json",
        headers={"X-Signal-Signature": _sign(raw)},
    )


@pytest.fixture
def app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
    os.environ["SIGNAL_BRIDGE_SECRET"] = SIGNAL_SECRET
    os.environ["GFCC_SIGNAL_INGEST_URL"] = ""
    os.environ["SIGNAL_INGEST_SECRET"] = ""
    from src.app import create_app
    _app = create_app("testing")
    yield _app
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def _register_user(client, email="signaler@test.com"):
    resp = client.post("/v1/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Signal Tester",
    })
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()


def test_valid_signature_consensus_match_completes_mission(client, app):
    """合法签 + consensus_match → 命中用户 → match mission 完成并发 XP。"""
    data = _register_user(client)
    user_id = data["user"]["id"]
    from src.db.manager import email_hash
    user_hash = email_hash("signaler@test.com")

    resp = _post(client, _envelope("consensus_match", user_hash, "nonce-1"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["matched"] is True
    assert body["mission_completed"] is True
    assert body["mission_id"] == "match"

    with app.app_context():
        assert app._db.get_game_profile(user_id)["xp"] == 50


def test_bad_signature_401(client):
    """坏签 → 401。"""
    raw = _json.dumps(_envelope("consensus_match", "deadbeef", "nonce-x")).encode("utf-8")
    resp = client.post(
        "/v1/game/signal-ingest",
        data=raw,
        content_type="application/json",
        headers={"X-Signal-Signature": "0" * 64},
    )
    assert resp.status_code == 401


def test_duplicate_nonce_no_double_reward(client, app):
    """同 (signal_type, user_email_hash, nonce) 不重复发 XP。"""
    data = _register_user(client)
    user_id = data["user"]["id"]
    from src.db.manager import email_hash
    user_hash = email_hash("signaler@test.com")

    env = _envelope("consensus_match", user_hash, "nonce-dup")
    r1 = _post(client, env)
    assert r1.status_code == 200
    assert r1.get_json()["mission_completed"] is True

    r2 = _post(client, env)  # 同一 nonce 重放
    assert r2.status_code == 200
    assert r2.get_json()["duplicate"] is True

    with app.app_context():
        assert app._db.get_game_profile(user_id)["xp"] == 50  # 只加一次


def test_second_signal_no_double_mission(client, app):
    """同一用户不同 nonce 二次 consensus_match：match mission 已完成，不再发 XP。"""
    data = _register_user(client)
    user_id = data["user"]["id"]
    from src.db.manager import email_hash
    user_hash = email_hash("signaler@test.com")

    r1 = _post(client, _envelope("consensus_match", user_hash, "nonce-a"))
    assert r1.get_json()["mission_completed"] is True

    r2 = _post(client, _envelope("consensus_match", user_hash, "nonce-b"))
    assert r2.status_code == 200
    assert r2.get_json()["mission_completed"] is False

    with app.app_context():
        assert app._db.get_game_profile(user_id)["xp"] == 50


def test_unknown_user_200(client):
    """email_hash 无匹配用户 → 仍 200，matched=False。"""
    from src.db.manager import email_hash
    unknown_hash = email_hash("nobody@test.com")
    resp = _post(client, _envelope("consensus_match", unknown_hash, "nonce-u"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["matched"] is False


def test_unknown_signal_type_ignored(client):
    """种子期非 consensus_match 类型 → 幂等记录后忽略。"""
    resp = _post(client, _envelope("some_other_signal", "deadbeef", "nonce-u2"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ignored"] is True


def test_missing_required_fields_400(client):
    """缺 nonce / user_email_hash → 400。"""
    raw = _json.dumps({"signal_type": "consensus_match"}).encode("utf-8")
    resp = client.post(
        "/v1/game/signal-ingest",
        data=raw,
        content_type="application/json",
        headers={"X-Signal-Signature": _sign(raw)},
    )
    assert resp.status_code == 400
