"""
JWT refresh after payment tier change tests.

Coverage:
  - stub upgrade returns new access_token
  - new token JWT payload includes updated tier
  - old token still works (require_auth reads tier from DB)
  - POST /v1/auth/refresh returns new valid token
  - refresh after upgrade → token contains new tier
  - consecutive upgrades → refresh stays in sync
  - email claim preserved after refresh
  - unauthenticated refresh → 401
"""
import json
import os
import tempfile

import pytest
import jwt

from src.app import create_app


@pytest.fixture(autouse=True)
def _clean_wechat_env():
    for key in ("WECHAT_MCHID", "WECHAT_APPID", "WECHAT_API_V3_KEY",
                "WECHAT_SERIAL_NO", "WECHAT_PRIVATE_KEY_PATH", "WECHAT_NOTIFY_URL"):
        os.environ.pop(key, None)
    yield


@pytest.fixture
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    os.environ["PAYMENT_STUB_MODE"] = "true"
    os.environ["JWT_EXPIRY_HOURS"] = "168"
    application = create_app("testing")
    yield application
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


def _register(c, email, password="secret123"):
    resp = c.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "name": "Test"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    return data["access_token"], data["user"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _decode_token(token, secret):
    return jwt.decode(token, secret, algorithms=["HS256"], issuer="looma")


# ── Basic refresh ──────────────────────────────────────────

class TestBasicRefresh:

    def test_refresh_returns_valid_token(self, client):
        """POST /v1/auth/refresh returns a valid JWT with correct claims."""
        token, user = _register(client, "refresh_basic@test.com")
        resp = client.post("/v1/auth/refresh", headers=_auth_headers(token))
        assert resp.status_code == 200
        new_token = resp.get_json()["access_token"]
        assert new_token  # non-empty token
        # Token can decode with correct sub
        secret = client.application.config["JWT_SECRET"]
        claims = _decode_token(new_token, secret)
        assert claims["sub"] == user["id"]

    def test_refresh_without_auth_returns_401(self, client):
        resp = client.post("/v1/auth/refresh")
        assert resp.status_code == 401

    def test_refresh_preserves_email_claim(self, client):
        """Email claim survives refresh."""
        token, user = _register(client, "refresh_email@test.com")
        # Original token has email
        secret = client.application.config["JWT_SECRET"]
        original = _decode_token(token, secret)
        assert original["email"] == "refresh_email@test.com"

        # Refresh
        resp = client.post("/v1/auth/refresh", headers=_auth_headers(token))
        new_token = resp.get_json()["access_token"]
        new_claims = _decode_token(new_token, secret)
        assert new_claims["email"] == "refresh_email@test.com"


# ── Upgrade + refresh ──────────────────────────────────────

class TestUpgradeRefresh:

    def test_stub_upgrade_returns_new_token(self, client):
        """Stub upgrade response includes new access_token."""
        token, _ = _register(client, "upgrade_token@test.com")
        resp = client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()
        assert resp.get_json()["tier"] == "supporter"

    def test_new_token_has_updated_tier(self, client):
        """Token returned by upgrade has updated tier in JWT payload."""
        token, _ = _register(client, "upgrade_tier_payload@test.com")
        resp = client.post(
            "/v1/payment/upgrade",
            json={"tier": "pro"},
            headers=_auth_headers(token),
        )
        new_token = resp.get_json()["access_token"]
        secret = client.application.config["JWT_SECRET"]
        claims = _decode_token(new_token, secret)
        assert claims["tier"] == "pro"

    def test_old_token_still_works_after_upgrade(self, client):
        """Old token still accessible — require_auth reads tier from DB."""
        token, _ = _register(client, "old_token@test.com")
        client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        # Old token still works for profile
        resp = client.get("/v1/auth/profile", headers=_auth_headers(token))
        assert resp.status_code == 200
        # Profile reflects new tier (read from DB, not JWT)
        assert resp.get_json()["tier"] == "supporter"

    def test_refresh_after_upgrade_returns_new_tier(self, client):
        """Refresh after tier upgrade → token contains new tier."""
        token, _ = _register(client, "refresh_upgrade@test.com")
        client.post(
            "/v1/payment/upgrade",
            json={"tier": "pro"},
            headers=_auth_headers(token),
        )
        resp = client.post("/v1/auth/refresh", headers=_auth_headers(token))
        new_token = resp.get_json()["access_token"]
        secret = client.application.config["JWT_SECRET"]
        claims = _decode_token(new_token, secret)
        assert claims["tier"] == "pro"

    def test_consecutive_upgrades_refresh_consistent(self, client):
        """Multiple consecutive upgrades → refresh always reflects latest."""
        token, _ = _register(client, "multi_upgrade@test.com")
        tiers = ["supporter", "pro"]

        for tier in tiers:
            client.post(
                "/v1/payment/upgrade",
                json={"tier": tier},
                headers=_auth_headers(token),
            )
            resp = client.post("/v1/auth/refresh", headers=_auth_headers(token))
            new_token = resp.get_json()["access_token"]
            secret = client.application.config["JWT_SECRET"]
            claims = _decode_token(new_token, secret)
            assert claims["tier"] == tier
            token = new_token

    def test_upgrade_then_profile_then_refresh(self, client):
        """Full chain: upgrade → profile checks → refresh → re-verify."""
        token, user = _register(client, "full_chain@test.com")
        assert user["tier"] == "free"

        # Upgrade
        client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )

        # Profile (from DB)
        profile = client.get("/v1/auth/profile", headers=_auth_headers(token))
        assert profile.get_json()["tier"] == "supporter"

        # Refresh
        resp = client.post("/v1/auth/refresh", headers=_auth_headers(token))
        new_token = resp.get_json()["access_token"]
        secret = client.application.config["JWT_SECRET"]
        claims = _decode_token(new_token, secret)
        assert claims["tier"] == "supporter"
        assert claims["sub"] == user["id"]

        # New token works
        resp2 = client.get("/v1/auth/profile", headers=_auth_headers(new_token))
        assert resp2.get_json()["tier"] == "supporter"

    def test_payment_status_after_upgrade(self, client):
        """GET /v1/payment/status shows active after upgrade + refresh."""
        token, _ = _register(client, "status_upgrade@test.com")
        # Free user
        resp = client.get("/v1/payment/status", headers=_auth_headers(token))
        assert resp.get_json()["tier"] == "free"
        assert resp.get_json()["status"] == "inactive"

        # Upgrade
        client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        resp = client.get("/v1/payment/status", headers=_auth_headers(token))
        assert resp.get_json()["tier"] == "supporter"
        assert resp.get_json()["status"] == "active"
