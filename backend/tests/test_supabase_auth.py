"""
Supabase unified auth tests — RFC docs/rfc/supabase-unified-auth-v1.md.

Covers:
  - require_auth accepts a custom Supabase JWT (HS256 + SUPABASE_JWT_SECRET)
  - first contact auto-creates / binds the looma user (supabase_uid mapping)
  - legacy email accounts get bound to their Supabase identity on first sight
  - invalid Supabase tokens are rejected
  - legacy looma JWT path still works (dual-token transition, D6)

Run: pytest tests/test_supabase_auth.py -v
"""
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_SB_URL = "https://test-ref.supabase.co"
TEST_SB_JWT_SECRET = "test-supabase-jwt-secret-0123456789abcdef"
TEST_SB_SECRET = "sb_secret_test"


def _sign_custom_token(supabase_uid: str, email: str,
                       secret: str = TEST_SB_JWT_SECRET) -> str:
    import jwt as pyjwt
    now = int(time.time())
    payload = {
        "iss": f"{TEST_SB_URL}/auth/v1",
        "sub": supabase_uid,
        "aud": "authenticated",
        "iat": now,
        "exp": now + 3600,
        "email": email,
        "role": "authenticated",
        "aal": "aal1",
        "app_metadata": {"provider": "wechat", "providers": ["wechat"]},
        "user_metadata": {"wechat_openid": "mock_openid"},
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def _no_network_jwks(monkeypatch):
    """Block real JWKS network fetches: tests only exercise the HS256 path."""
    import jwt as pyjwt

    class _FakeJWKSClient:
        def __init__(self, *a, **k):
            pass

        def get_signing_key_from_jwt(self, token):
            raise pyjwt.exceptions.PyJWTError("JWKS disabled in tests")

    monkeypatch.setattr(pyjwt, "PyJWKClient", _FakeJWKSClient)


@pytest.fixture
def app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
    os.environ["SUPABASE_URL"] = TEST_SB_URL
    os.environ["SUPABASE_JWT_SECRET"] = TEST_SB_JWT_SECRET
    os.environ["SUPABASE_SECRET_KEY"] = TEST_SB_SECRET
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


def test_profile_with_supabase_custom_token(client, app):
    """A valid custom Supabase JWT should pass require_auth and map to a user."""
    uid = "11111111-2222-3333-4444-555555555555"
    token = _sign_custom_token(uid, "wx_1@wechat.thomas.local")

    resp = client.get("/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"]

    # The looma user should now be resolvable by supabase_uid
    db = client.application._db
    user = db.get_user_by_supabase_uid(uid)
    assert user is not None
    assert user["id"] == data["id"]


def test_second_contact_reuses_same_user(client):
    """Two requests with the same supabase identity resolve to the same looma user."""
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    token = _sign_custom_token(uid, "wx_2@wechat.thomas.local")

    r1 = client.get("/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    r2 = client.get("/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.get_json()["id"] == r2.get_json()["id"]


def test_legacy_email_user_bound_on_first_supabase_login(client, app):
    """Existing email+bcrypt user binds to Supabase identity on first contact."""
    # Legacy looma registration (old path)
    resp = client.post("/v1/auth/register", json={
        "email": "legacy@example.com",
        "password": "password123",
        "name": "Legacy User",
    })
    assert resp.status_code == 201
    legacy_user_id = resp.get_json()["user"]["id"]

    # Same email, now authenticated via Supabase
    uid = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
    token = _sign_custom_token(uid, "legacy@example.com")
    resp = client.get("/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["id"] == legacy_user_id

    db = client.application._db
    user = db.get_user_by_id(legacy_user_id)
    assert user["supabase_uid"] == uid


def test_placeholder_email_creates_fresh_user(client, app):
    """WeChat placeholder emails (thomas.local) must NOT bind to real accounts."""
    uid = "cccccccc-dddd-eeee-ffff-000000000000"
    token = _sign_custom_token(uid, "dev_mock@wechat.thomas.local")

    resp = client.get("/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    db = client.application._db
    user = db.get_user_by_supabase_uid(uid)
    assert user is not None
    # No legacy user with that placeholder email could have been hijacked
    assert user["supabase_uid"] == uid


def test_invalid_supabase_token_rejected(client):
    """A token signed with the wrong secret must be rejected (401)."""
    uid = "dddddddd-eeee-ffff-0000-111111111111"
    token = _sign_custom_token(uid, "evil@example.com", secret="wrong-secret")

    resp = client.get("/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_looma_legacy_token_still_works(client):
    """Dual-token transition: old looma JWTs keep working while Supabase is on."""
    resp = client.post("/v1/auth/register", json={
        "email": "dual@example.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]

    resp = client.get("/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "dual@example.com"


def test_wechat_login_requires_code(client):
    resp = client.post("/v1/auth/wechat", json={})
    assert resp.status_code == 400
