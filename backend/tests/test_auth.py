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
    """Default / Supabase bridge still 501 until that path lands."""
    resp = client.post("/v1/auth/bridge", json={})
    assert resp.status_code == 501
    data = resp.get_json()
    assert data["error"] == "not_implemented"


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
        conn.execute("DELETE FROM user_identities WHERE user_id = ?", (user_id,))
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


def test_bind_wechat_dev_mode_joins_email_account():
    """WECHAT_DEV_MODE 下 /v1/auth/bind 不调 code2session，并用邮箱密码认人。

    微信先建出来的人和邮箱注册的人，绑定后必须是同一个 user id。
    密码不对不得改挂 openid。同一个 openid 不能再挂到第三人。
    """
    from src.app import create_app

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    prev_dev_mode = os.environ.get("WECHAT_DEV_MODE")
    try:
        os.environ["DATABASE_PATH"] = path
        os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
        os.environ["WECHAT_DEV_MODE"] = "true"
        for key in ("WECHAT_APPID", "WECHAT_SECRET", "WECHAT_APP_SECRET",
                    "SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_JWT_SECRET"):
            os.environ.pop(key, None)

        c = create_app("testing").test_client()

        resp = c.post("/v1/auth/register", json={
            "email": "bind-dev@test.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        email_user = resp.get_json()["user"]["id"]

        resp = c.post("/v1/auth/wechat", json={"code": "mock-wx-code"})
        assert resp.status_code == 200, resp.get_json()
        wechat_token = resp.get_json()["access_token"]
        wechat_user = resp.get_json()["user"]["id"]
        assert wechat_user != email_user

        resp = c.post(
            "/v1/auth/bind",
            json={"code": "mock-wx-code", "email": "bind-dev@test.com", "password": "wrong-pass"},
            headers={"Authorization": f"Bearer {wechat_token}"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "unauthorized"

        resp = c.post(
            "/v1/auth/bind",
            json={"code": "mock-wx-code", "email": "bind-dev@test.com", "password": "password123"},
            headers={"Authorization": f"Bearer {wechat_token}"},
        )
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body["joined_existing"] is True
        assert body["user"]["id"] == email_user
        assert body["user"]["email"] == "bind-dev@test.com"

        resp = c.post("/v1/auth/login", json={
            "email": "bind-dev@test.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert resp.get_json()["user"]["id"] == email_user

        resp = c.post("/v1/auth/wechat", json={"code": "mock-wx-code"})
        assert resp.status_code == 200
        assert resp.get_json()["user"]["id"] == email_user

        resp = c.post("/v1/auth/register", json={
            "email": "bind-dev-2@test.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        token2 = resp.get_json()["access_token"]
        resp = c.post(
            "/v1/auth/bind",
            json={"code": "mock-wx-code", "email": "bind-dev-2@test.com", "password": "password123"},
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


def test_bind_wechat_saves_new_email_on_wechat_user():
    """邮箱还没人注册时，绑定把邮箱写到当前微信用户上，iOS 再用这组密码能进同一个人。"""
    from src.app import create_app

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    prev_dev_mode = os.environ.get("WECHAT_DEV_MODE")
    try:
        os.environ["DATABASE_PATH"] = path
        os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
        os.environ["WECHAT_DEV_MODE"] = "true"
        for key in ("WECHAT_APPID", "WECHAT_SECRET", "WECHAT_APP_SECRET",
                    "SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_JWT_SECRET"):
            os.environ.pop(key, None)

        c = create_app("testing").test_client()
        resp = c.post("/v1/auth/wechat", json={"code": "fresh-wx"})
        assert resp.status_code == 200, resp.get_json()
        wechat_user = resp.get_json()["user"]["id"]
        token = resp.get_json()["access_token"]

        resp = c.post(
            "/v1/auth/bind",
            json={"code": "fresh-wx", "email": "new-on-wechat@test.com", "password": "password123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["joined_existing"] is False
        assert resp.get_json()["user"]["id"] == wechat_user

        resp = c.post("/v1/auth/login", json={
            "email": "new-on-wechat@test.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert resp.get_json()["user"]["id"] == wechat_user
    finally:
        if prev_dev_mode is None:
            os.environ.pop("WECHAT_DEV_MODE", None)
        else:
            os.environ["WECHAT_DEV_MODE"] = prev_dev_mode
        try:
            os.unlink(path)
        except OSError:
            pass


def test_wechat_new_user_does_not_depend_on_supabase():
    """SUPABASE 三件套配置齐全时，微信新用户也必须走 looma 账本（与华为同一条）。

    旧实现此时会调 Supabase Admin API：key 失效即 502 identity provider
    unavailable，小程序整个挡在登录之外；且签的是 Supabase custom token
    （sub=Supabase UUID），与鸿蒙端认的不是同一个人。现在无论 Supabase 是否
    配置，新 openid 一律 user_identities 找/建 + looma JWT。这里把三件套写成
    假地址——若回归到 Supabase 分支，本用例会因上游失败而挂。
    """
    from src.app import create_app
    from src.thomas_core.auth.jwt_handler import verify_token

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    saved = {k: os.environ.get(k) for k in
             ("WECHAT_DEV_MODE", "SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_JWT_SECRET")}
    try:
        os.environ["DATABASE_PATH"] = path
        os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
        os.environ["WECHAT_DEV_MODE"] = "true"
        os.environ["SUPABASE_URL"] = "https://supabase.invalid"
        os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_invalid"
        os.environ["SUPABASE_JWT_SECRET"] = "invalid-supabase-jwt-secret"

        c = create_app("testing").test_client()

        resp = c.post("/v1/auth/wechat", json={"code": "no-supabase"})
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        token = body["access_token"]
        with c.application.app_context():
            payload = verify_token(token)
        assert payload["iss"] == "looma"
        assert payload["sub"] == body["user"]["id"]

        # 同一个 openid 再来一次，必须还是这一个人（认人稳定，不产生第二个号）
        resp = c.post("/v1/auth/wechat", json={"code": "no-supabase"})
        assert resp.status_code == 200
        assert resp.get_json()["user"]["id"] == body["user"]["id"]
    finally:
        for key, prev in saved.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        try:
            os.unlink(path)
        except OSError:
            pass
