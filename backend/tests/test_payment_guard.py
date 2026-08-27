"""Tests for payment stub guard and WeChat Pay order flow."""
import os
import tempfile
from contextlib import contextmanager
import pytest

from src.app import create_app


@pytest.fixture
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    os.environ["PAYMENT_STUB_MODE"] = "true"
    application = create_app("testing")
    yield application
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
    return resp.get_json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def _make_app_client(stub_mode="true"):
    """创建带指定 stub_mode 的独立 app+client。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["PAYMENT_STUB_MODE"] = stub_mode
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    try:
        app = create_app("testing")
        yield app.test_client()
    finally:
        os.environ["PAYMENT_STUB_MODE"] = "true"
        if os.path.exists(path):
            os.unlink(path)


class TestStubGuard:

    def test_stub_upgrade_succeeds_by_default(self, client):
        token = _register(client, "stub_on@test.com")
        resp = client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["tier"] == "supporter"

    def test_stub_upgrade_blocked_when_disabled(self):
        with _make_app_client(stub_mode="false") as c:
            token = _register(c, "stub_off@test.com")
            resp = c.post(
                "/v1/payment/upgrade",
                json={"tier": "supporter"},
                headers=_auth_headers(token),
            )
            assert resp.status_code == 402
            assert resp.get_json()["error"] == "payment_required"

    def test_wechat_order_blocked_in_stub_mode(self, client):
        token = _register(client, "wx_stub@test.com")
        resp = client.post(
            "/v1/payment/wechat/order",
            json={"tier": "supporter", "trade_type": "NATIVE"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "stub_mode"

    def test_wechat_order_needs_credentials(self):
        os.environ.pop("WECHAT_MCHID", None)
        os.environ.pop("WECHAT_API_V3_KEY", None)
        with _make_app_client(stub_mode="false") as c:
            token = _register(c, "wx_nocred@test.com")
            resp = c.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "NATIVE"},
                headers=_auth_headers(token),
            )
            assert resp.status_code == 503
            assert resp.get_json()["error"] == "payment_not_configured"

    def test_cannot_downgrade(self, client):
        token = _register(client, "nodown@test.com")
        client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        resp = client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400


class TestOrderLifecycle:

    def test_order_created_on_stub_upgrade(self, client):
        token = _register(client, "order_audit@test.com")
        resp = client.post(
            "/v1/payment/upgrade",
            json={"tier": "pro"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        profile = client.get("/v1/auth/profile", headers=_auth_headers(token))
        assert profile.get_json()["tier"] == "pro"

    def test_wechat_notify_bad_body_handled(self, client):
        resp = client.post(
            "/v1/payment/wechat/notify",
            data="not valid json",
            content_type="application/json",
        )
        assert resp.status_code in (200, 500)

    def test_plans_response_excludes_stub_mode(self, client):
        """stub_mode must not leak to public API responses."""
        resp = client.get("/v1/payment/plans")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stub_mode" not in data

    def test_payment_status_excludes_stub_mode(self, client):
        token = _register(client, "status_test@test.com")
        resp = client.get("/v1/payment/status", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stub_mode" not in data
        assert data["tier"] == "free"
