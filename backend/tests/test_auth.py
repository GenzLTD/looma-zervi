"""
Basic test for auth and health endpoints.
Run: pytest tests/test_auth.py -v
"""
import pytest
import sys
import os
import tempfile

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def app():
    """Create a test app with a temporary database file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
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


def test_health(client):
    """Health check should return 200 and provider config booleans (no secrets)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] in ("ok", "degraded")
    assert "providers_configured" in data
    assert set(data["providers_configured"]) >= {"openai", "deepseek", "ollama"}
    assert isinstance(data["providers_configured"]["openai"], bool)
    assert isinstance(data["providers_configured"]["deepseek"], bool)
    assert "qcc_configured" in data
    assert isinstance(data["qcc_configured"], bool)
    assert "llm_provider_order" in data
    # Must never leak key material
    blob = str(data).lower()
    assert "sk-" not in blob
    assert "bearer " not in blob


def test_register_missing_fields(client):
    """Register without email/password should return 400."""
    resp = client.post("/v1/auth/register", json={})
    assert resp.status_code == 400


def test_register_short_password(client):
    """Register with short password should return 400."""
    resp = client.post("/v1/auth/register", json={"email": "test@test.com", "password": "123"})
    assert resp.status_code == 400


def test_register_and_login(client):
    """Register then login should work."""
    # Register
    resp = client.post("/v1/auth/register", json={
        "email": "test@test.com",
        "password": "password123",
        "name": "Test User",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@test.com"

    # Login
    resp = client.post("/v1/auth/login", json={
        "email": "test@test.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data


def test_login_wrong_password(client):
    """Login with wrong password should return 401."""
    client.post("/v1/auth/register", json={
        "email": "test@test.com",
        "password": "password123",
    })
    resp = client.post("/v1/auth/login", json={
        "email": "test@test.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_profile_requires_auth(client):
    """Profile endpoint should require auth."""
    resp = client.get("/v1/auth/profile")
    assert resp.status_code == 401


def test_profile_with_token(client):
    """Profile endpoint should work with valid token."""
    resp = client.post("/v1/auth/register", json={
        "email": "test@test.com",
        "password": "password123",
        "name": "Test User",
    })
    token = resp.get_json()["access_token"]

    resp = client.get("/v1/auth/profile", headers={
        "Authorization": f"Bearer {token}"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["email"] == "test@test.com"


def test_bridge_not_implemented(client):
    """Supabase bridge should return 501 in MVP."""
    resp = client.post("/v1/auth/bridge", json={})
    assert resp.status_code == 501


def test_require_auth_rejects_unknown_user(client):
    """JWT for deleted user should return 401 on protected routes."""
    resp = client.post("/v1/auth/register", json={
        "email": "ghost@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    user_id = resp.get_json()["user"]["id"]

    db = client.application._db
    with db.get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    resp = client.get("/v1/auth/profile", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 401


def test_payment_upgrade_returns_fresh_token(client):
    """Upgrade should return access_token with updated tier claim."""
    resp = client.post("/v1/auth/register", json={
        "email": "upgrade@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]

    resp = client.post(
        "/v1/payment/upgrade",
        json={"tier": "pro"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["tier"] == "pro"

    resp = client.get("/v1/payment/status", headers={
        "Authorization": f"Bearer {data['access_token']}",
    })
    assert resp.status_code == 200
    assert resp.get_json()["tier"] == "pro"
