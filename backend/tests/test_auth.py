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
    # 本机 .env 可能有 PAYMENT_STUB_MODE=false（Stripe 联调），别渗进测试
    os.environ["PAYMENT_STUB_MODE"] = "true"
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


def test_bind_wechat_dev_mode_short_circuit():
    """WECHAT_DEV_MODE 下 /v1/auth/bind 与 /v1/auth/wechat 同约定：不调 code2session。

    本机没有 AppID/Secret 时绑定链路也应跑通（由 code 派生 mock openid），
    否则绑定邮箱永远 400，小程序全量验证里这一项就只能长期挂起。
    小程序多传的 email/password 该接口不读，也不得因此报错。
    """
    from src.app import create_app

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    prev_dev_mode = os.environ.get("WECHAT_DEV_MODE")
    try:
        os.environ["DATABASE_PATH"] = path
        os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
        os.environ["WECHAT_DEV_MODE"] = "true"
        for key in ("WECHAT_APPID", "WECHAT_SECRET"):
            os.environ.pop(key, None)

        c = create_app("testing").test_client()

        resp = c.post("/v1/auth/register", json={
            "email": "bind-dev@test.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        token = resp.get_json()["access_token"]

        resp = c.post(
            "/v1/auth/bind",
            json={"code": "mock-wx-code", "email": "ignored@test.com", "password": "ignored"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["message"] == "WeChat account bound successfully"

        # 同一个 mock openid 绑给另一个用户必须 409（dev 模式下 openid=dev_<code>，
        # 两个账号用同一个 code 即同一个 openid）
        resp = c.post("/v1/auth/register", json={
            "email": "bind-dev-2@test.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        token2 = resp.get_json()["access_token"]
        resp = c.post(
            "/v1/auth/bind",
            json={"code": "mock-wx-code"},
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "conflict"
    finally:
        if prev_dev_mode is None:
            os.environ.pop("WECHAT_DEV_MODE", None)
        else:
            os.environ["WECHAT_DEV_MODE"] = prev_dev_mode
        try:
            os.unlink(path)
        except OSError:
            pass
