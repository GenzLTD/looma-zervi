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

    def test_wechat_order_in_stub_mode_returns_simulated_order(self, client):
        """双主体定案后：stub 不再 400 短路，而是 201 发模拟二维码
        （商户号审批前的全链联调用，见 docs/收款主体架构定案）。"""
        token = _register(client, "wx_stub@test.com")
        resp = client.post(
            "/v1/payment/wechat/order",
            json={"tier": "supporter", "trade_type": "NATIVE"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["stub_mode"] is True
        assert body["qr_code_url"].startswith("weixin://wxpay/stub/")

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

    def test_stub_mode_lives_on_providers_only(self, client):
        """契约 v1.4.0：/providers 是 stub_mode 的权威源，公开面不许带。

        反向钉住 plans/status 的同时，正向钉住 providers 真的会返回布尔值——
        只钉「不带」是不够的：哪天 providers 少返回这个字段，客户端就会退回
        靠缺失值推断的老毛病。
        """
        assert "stub_mode" not in client.get("/v1/payment/plans").get_json()
        token = _register(client, "disclosure@test.com")
        assert "stub_mode" not in client.get(
            "/v1/payment/status", headers=_auth_headers(token)
        ).get_json()

        providers = client.get("/v1/payment/providers")
        assert providers.status_code == 200
        assert providers.get_json()["stub_mode"] is True

    def test_providers_stub_mode_is_false_when_disabled(self):
        with _make_app_client(stub_mode="false") as c:
            resp = c.get("/v1/payment/providers")
            assert resp.status_code == 200
            assert resp.get_json()["stub_mode"] is False

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
