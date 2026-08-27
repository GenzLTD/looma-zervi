"""
Signal Bridge 3 outbound (T3) tests — personality_beacon egress.

Run: pytest tests/test_personality_beacon.py -v
"""
import hashlib as _hashlib
import hmac as _hmac
import json as _json
import os
import sys
import tempfile
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SIGNAL_SECRET = "test-signal-bridge-secret-2026"
DEMOPPI_URL = "http://127.0.0.1:3000/api/signal/ingest"


@pytest.fixture
def app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
    os.environ["SIGNAL_BRIDGE_SECRET"] = SIGNAL_SECRET
    os.environ["DEMOPPI_SIGNAL_INGEST_URL"] = DEMOPPI_URL
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


def _register_user(client, email="beacon@test.com"):
    resp = client.post("/v1/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Beacon Tester",
    })
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()


def _auth_headers(data):
    token = data.get("access_token") or data.get("token")
    assert token, data
    return {"Authorization": f"Bearer {token}"}


# ── pure helpers ──

def test_parse_personality_detail_json():
    from src.api.routes.game_routes import _parse_personality_detail
    traits, score = _parse_personality_detail('{"traits": ["creative", "deep"], "score": 0.87}')
    assert traits == ["creative", "deep"]
    assert score == 0.87


def test_parse_personality_detail_plain_text():
    from src.api.routes.game_routes import _parse_personality_detail
    traits, score = _parse_personality_detail("星云艺术家 · 自由探索")
    assert traits == []
    assert score is None


def test_parse_personality_detail_empty():
    from src.api.routes.game_routes import _parse_personality_detail
    assert _parse_personality_detail("") == ([], None)
    assert _parse_personality_detail(None) == ([], None)


def test_build_envelope_structure():
    from src.api.routes.game_routes import _build_personality_beacon_envelope
    env = _build_personality_beacon_envelope(
        "hash123", "星云艺术家", ["creative"], 0.9,
        nonce="fixed-nonce", timestamp="2026-08-14T00:00:00.000Z",
    )
    assert env["signal_type"] == "personality_beacon"
    assert env["user_email_hash"] == "hash123"
    assert env["data"] == {
        "personality_type": "星云艺术家",
        "traits": ["creative"],
        "score": 0.9,
    }
    assert env["nonce"] == "fixed-nonce"
    assert env["timestamp"] == "2026-08-14T00:00:00.000Z"


def test_build_envelope_auto_nonce_timestamp():
    from src.api.routes.game_routes import _build_personality_beacon_envelope
    env = _build_personality_beacon_envelope("hash", "星云艺术家", [], None)
    assert env["nonce"]
    assert env["timestamp"].endswith("Z")


# ── egress behavior (mock urllib) ──

class _FakeResp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b"{}"


def test_egress_sends_signed_envelope(client, app, monkeypatch):
    from src.api.routes import game_routes as gr
    from src.db.manager import email_hash

    data = _register_user(client)
    user_id = data["user"]["id"]
    user_hash = email_hash("beacon@test.com")

    captured = {}

    def fake_urlopen(req, timeout=5):
        captured["url"] = req.full_url
        captured["body"] = req.data
        # urllib add_header capitalizes the key → "X-signal-signature"
        captured["sig"] = req.get_header("X-signal-signature")
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with app.app_context():
        gr._send_personality_beacon(
            app._db, user_id, "星云艺术家",
            '{"traits": ["creative", "deep"], "score": 0.87}',
        )

    assert captured["url"] == DEMOPPI_URL
    body = _json.loads(captured["body"].decode("utf-8"))
    assert body["signal_type"] == "personality_beacon"
    assert body["user_email_hash"] == user_hash
    assert body["data"]["personality_type"] == "星云艺术家"
    assert body["data"]["traits"] == ["creative", "deep"]
    assert body["data"]["score"] == 0.87
    # 无明文 email，只有 hash
    assert "beacon@test.com" not in captured["body"].decode("utf-8")
    # 签名 = HMAC(raw_body, secret)
    expected_sig = _hmac.new(
        SIGNAL_SECRET.encode(), captured["body"], _hashlib.sha256
    ).hexdigest()
    assert captured["sig"] == expected_sig


def test_egress_noop_when_url_missing(client, app, monkeypatch):
    from src.api.routes import game_routes as gr

    data = _register_user(client)
    user_id = data["user"]["id"]
    sent = {"called": False}

    def fake_urlopen(req, timeout=5):
        sent["called"] = True
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with app.app_context():
        app.config["DEMOPPI_SIGNAL_INGEST_URL"] = ""
        gr._send_personality_beacon(app._db, user_id, "星云艺术家", "")

    assert sent["called"] is False


def test_egress_noop_when_no_secret(client, app, monkeypatch):
    from src.api.routes import game_routes as gr

    data = _register_user(client)
    user_id = data["user"]["id"]
    sent = {"called": False}

    def fake_urlopen(req, timeout=5):
        sent["called"] = True
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with app.app_context():
        app.config["SIGNAL_BRIDGE_SECRET"] = ""
        gr._send_personality_beacon(app._db, user_id, "星云艺术家", "")

    assert sent["called"] is False


def test_egress_noop_when_unknown_user(client, app, monkeypatch):
    from src.api.routes import game_routes as gr

    _register_user(client)  # ensure app._db is wired before direct helper call

    sent = {"called": False}

    def fake_urlopen(req, timeout=5):
        sent["called"] = True
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with app.app_context():
        gr._send_personality_beacon(app._db, "no-such-user", "星云艺术家", "")

    assert sent["called"] is False


def test_egress_failure_does_not_raise(client, app, monkeypatch):
    from src.api.routes import game_routes as gr

    data = _register_user(client)
    user_id = data["user"]["id"]

    def fake_urlopen(req, timeout=5):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with app.app_context():
        # 不应抛出异常
        gr._send_personality_beacon(app._db, user_id, "星云艺术家", "")


# ── end-to-end: profile-sync triggers egress ──

def test_profile_sync_triggers_signed_egress(client, app, monkeypatch):
    from src.db.manager import email_hash

    data = _register_user(client)
    user_hash = email_hash("beacon@test.com")

    captured = {}

    def fake_urlopen(req, timeout=5):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["sig"] = req.get_header("X-signal-signature")
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    resp = client.post(
        "/v1/game/profile-sync",
        json={
            "personality_type": "星云艺术家",
            "personality_detail": '{"traits": ["creative", "deep"], "score": 0.87}',
        },
        headers=_auth_headers(data),
    )
    assert resp.status_code == 200, resp.get_json()

    assert captured.get("url") == DEMOPPI_URL
    body = _json.loads(captured["body"].decode("utf-8"))
    assert body["signal_type"] == "personality_beacon"
    assert body["user_email_hash"] == user_hash
    assert body["data"]["personality_type"] == "星云艺术家"
    assert body["data"]["traits"] == ["creative", "deep"]
    assert body["data"]["score"] == 0.87
    assert "beacon@test.com" not in captured["body"].decode("utf-8")
    expected_sig = _hmac.new(
        SIGNAL_SECRET.encode(), captured["body"], _hashlib.sha256
    ).hexdigest()
    assert captured["sig"] == expected_sig
