"""GFCC chain-B fan-out mapping + signed POST.

Run: pytest tests/test_gfcc_fanout.py -v
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

from src.signal_bridge.gfcc_fanout import (  # noqa: E402
    map_personality_type,
    post_gfcc_signal,
    send_gfcc_personality_beacon,
    to_gfcc_personality_beacon_envelope,
)

HASH_A = "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"
SECRET = "dev-signal-secret-20260824"
GFCC_URL = "http://127.0.0.1:5211/v1/signal-ingest"


def test_map_planetx_labels_to_mbti():
    assert map_personality_type("星云艺术家") == "ENFP"
    assert map_personality_type("黑洞程序员") == "INTJ"
    assert map_personality_type("intj") == "INTJ"
    assert map_personality_type("未知人格") is None


def test_to_gfcc_envelope_maps_fields():
    mapped = to_gfcc_personality_beacon_envelope(
        HASH_A,
        "星云艺术家",
        ["creative", "deep"],
        0.87,
        nonce="n1n1n1n1",
        timestamp="2026-08-24T00:00:00.000Z",
    )
    assert "envelope" in mapped
    env = mapped["envelope"]
    assert env["signal_type"] == "personality_beacon"
    assert env["user_id_hash"] == HASH_A
    assert "user_email_hash" not in env
    assert "data" not in env
    assert env["payload"] == {
        "personality_type": "ENFP",
        "source": "planetx",
        "traits": [
            {"name": "creative", "score": 1.0},
            {"name": "deep", "score": 1.0},
        ],
        "assessment_score": 0.87,
        "generated_at": "2026-08-24T00:00:00.000Z",
    }


def test_to_gfcc_skips_unmapped_type():
    mapped = to_gfcc_personality_beacon_envelope(
        HASH_A, "未知人格", [], None, nonce="n1n1n1n1",
    )
    assert mapped == {"skip": "personality_type_unmapped"}


def test_to_gfcc_skips_short_hash():
    mapped = to_gfcc_personality_beacon_envelope(
        "hash123", "星云艺术家", [], None, nonce="n1n1n1n1",
    )
    assert mapped == {"skip": "user_id_hash_not_64_hex"}


class _FakeResp:
    def __init__(self, body=b'{"status":"stored","signal_id":"s1"}', status=200):
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def test_post_signs_x_signature(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=5):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["sig"] = req.get_header("X-signature")
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    mapped = to_gfcc_personality_beacon_envelope(
        HASH_A, "星云艺术家", [], None, nonce="n1n1n1n1",
    )
    res = post_gfcc_signal(mapped["envelope"], GFCC_URL, SECRET, max_retries=0)
    assert res["ok"] is True
    assert captured["url"] == GFCC_URL
    expected = _hmac.new(SECRET.encode(), captured["body"], _hashlib.sha256).hexdigest()
    assert captured["sig"] == expected
    body = _json.loads(captured["body"].decode("utf-8"))
    assert body["payload"]["personality_type"] == "ENFP"
    assert body["payload"]["source"] == "planetx"


def test_send_skips_without_posting(monkeypatch):
    sent = {"called": False}

    def fake_urlopen(req, timeout=5):
        sent["called"] = True
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = send_gfcc_personality_beacon(
        HASH_A, "未知人格", [], None, nonce="n1n1n1n1",
        url=GFCC_URL, secret=SECRET,
    )
    assert res["skipped"] is True
    assert sent["called"] is False


@pytest.fixture
def app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
    os.environ["SIGNAL_BRIDGE_SECRET"] = "test-signal-bridge-secret-2026"
    os.environ["DEMOPPI_SIGNAL_INGEST_URL"] = "http://127.0.0.1:3000/api/signal/ingest"
    os.environ["GFCC_SIGNAL_INGEST_URL"] = GFCC_URL
    os.environ["SIGNAL_INGEST_SECRET"] = SECRET
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


def test_profile_sync_fans_out_to_gfcc(client, app, monkeypatch):
    from src.db.manager import email_hash

    resp = client.post("/v1/auth/register", json={
        "email": "beacon@test.com",
        "password": "password123",
        "name": "Beacon Tester",
    })
    assert resp.status_code in (200, 201), resp.get_json()
    data = resp.get_json()
    token = data.get("access_token") or data.get("token")
    user_hash = email_hash("beacon@test.com")

    captured = []

    def fake_urlopen(req, timeout=5):
        captured.append({
            "url": req.full_url,
            "sig_bridge": req.get_header("X-signal-signature"),
            "sig_gfcc": req.get_header("X-signature"),
            "body": req.data,
        })
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    sync = client.post(
        "/v1/game/profile-sync",
        json={"personality_type": "星云艺术家"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sync.status_code == 200, sync.get_json()
    assert len(captured) == 2
    urls = {c["url"] for c in captured}
    assert "http://127.0.0.1:3000/api/signal/ingest" in urls
    assert GFCC_URL in urls
    gfcc = next(c for c in captured if c["url"] == GFCC_URL)
    assert gfcc["sig_gfcc"]
    assert not gfcc["sig_bridge"]
    body = _json.loads(gfcc["body"].decode("utf-8"))
    assert body["user_id_hash"] == user_hash
    assert body["payload"]["personality_type"] == "ENFP"
    assert body["payload"]["source"] == "planetx"
    expected = _hmac.new(SECRET.encode(), gfcc["body"], _hashlib.sha256).hexdigest()
    assert gfcc["sig_gfcc"] == expected
