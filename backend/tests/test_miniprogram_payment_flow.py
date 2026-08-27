"""
Miniprogram payment full-chain integration tests.

Simulates the complete miniprogram payment flow:
  Phase A (stub): wechat login → plans → stub upgrade → profile → refresh
  Phase B (production): wechat login → JSAPI order → notify → refresh → profile

Coverage:
  - wechat login returns free tier user
  - stub full chain: login → plans → upgrade → profile → refresh
  - upgrade to pro chain
  - stub downgrade prevention
  - plans CNY/USD region
  - JSAPI response structure compatible with wx.requestPayment
  - production full chain: order → notify → refresh → profile → status
"""
import json
import os
import tempfile
from unittest.mock import patch

import pytest
import jwt

from src.app import create_app
from src.payment.wechat_pay import WeChatOrderResult


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _decode_token(token, secret):
    return jwt.decode(token, secret, algorithms=["HS256"], issuer="looma")


# ── Shared fixtures ────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_wechat_env():
    for key in ("WECHAT_MCHID", "WECHAT_APPID", "WECHAT_API_V3_KEY",
                "WECHAT_SERIAL_NO", "WECHAT_PRIVATE_KEY_PATH", "WECHAT_NOTIFY_URL"):
        os.environ.pop(key, None)
    yield


@pytest.fixture
def app():
    """Stub mode + temp DB for Phase A tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    os.environ["PAYMENT_STUB_MODE"] = "true"
    os.environ["WECHAT_DEV_MODE"] = "true"
    os.environ["JWT_EXPIRY_HOURS"] = "168"
    application = create_app("testing")
    yield application
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


# ── Phase B production fixture ─────────────────────────────

@pytest.fixture
def prod_app():
    """Stub_mode=false + temp DB + fake credentials."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    os.environ["PAYMENT_STUB_MODE"] = "false"
    os.environ["WECHAT_MCHID"] = "1234567890"
    os.environ["WECHAT_APPID"] = "wx_test_appid"
    os.environ["WECHAT_API_V3_KEY"] = "32byteslongsecretkeyforwechatpay"
    os.environ["WECHAT_SERIAL_NO"] = "TEST_SERIAL"
    os.environ["WECHAT_PRIVATE_KEY_PATH"] = ""
    os.environ["WECHAT_NOTIFY_URL"] = "https://test.example.com/notify"
    os.environ["WECHAT_DEV_MODE"] = "true"
    os.environ["JWT_EXPIRY_HOURS"] = "168"
    application = create_app("testing")
    yield application
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def prod_client(prod_app):
    return prod_app.test_client()


# ── Phase A: Stub mode full chain ──────────────────────────

class TestStubFlow:

    def test_wechat_login_returns_free_user(self, client):
        """WeChat login gives a free tier user."""
        resp = client.post("/v1/auth/wechat", json={"code": "mp_test_001"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert data["user"]["tier"] == "free"

    def test_full_stub_upgrade_chain(self, client):
        """Login → plans → upgrade to supporter → profile → refresh."""
        # 1. WeChat login
        resp = client.post("/v1/auth/wechat", json={"code": "mp_full_001"})
        token = resp.get_json()["access_token"]
        assert resp.get_json()["user"]["tier"] == "free"

        # 2. Plans (CN region)
        plans = client.get("/v1/payment/plans?region=CN")
        assert plans.status_code == 200
        assert plans.get_json()["currency"] == "CNY"

        # 3. Stub upgrade to supporter
        upgrade = client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        assert upgrade.status_code == 200
        assert upgrade.get_json()["tier"] == "supporter"

        # 4. Profile shows new tier
        profile = client.get("/v1/auth/profile", headers=_auth_headers(token))
        assert profile.get_json()["tier"] == "supporter"

        # 5. Refresh token has new tier
        refresh = client.post("/v1/auth/refresh", headers=_auth_headers(token))
        new_token = refresh.get_json()["access_token"]
        secret = client.application.config["JWT_SECRET"]
        claims = _decode_token(new_token, secret)
        assert claims["tier"] == "supporter"

    def test_stub_upgrade_to_pro(self, client):
        """Login → stub upgrade to pro → profile confirms."""
        resp = client.post("/v1/auth/wechat", json={"code": "mp_pro_001"})
        token = resp.get_json()["access_token"]

        upgrade = client.post(
            "/v1/payment/upgrade",
            json={"tier": "pro"},
            headers=_auth_headers(token),
        )
        assert upgrade.status_code == 200
        assert upgrade.get_json()["tier"] == "pro"

        profile = client.get("/v1/auth/profile", headers=_auth_headers(token))
        assert profile.get_json()["tier"] == "pro"

    def test_stub_downgrade_blocked(self, client):
        """Cannot downgrade via stub upgrade."""
        resp = client.post("/v1/auth/wechat", json={"code": "mp_downgrade_001"})
        token = resp.get_json()["access_token"]

        # Upgrade to pro
        client.post(
            "/v1/payment/upgrade",
            json={"tier": "pro"},
            headers=_auth_headers(token),
        )

        # Try downgrade
        downgrade = client.post(
            "/v1/payment/upgrade",
            json={"tier": "supporter"},
            headers=_auth_headers(token),
        )
        assert downgrade.status_code == 400
        assert "downgrade" in downgrade.get_json()["message"].lower()

    def test_plans_cny_vs_usd(self, client):
        """Plans endpoint returns correct currency per region."""
        cny = client.get("/v1/payment/plans?region=CN")
        assert cny.get_json()["currency"] == "CNY"

        usd = client.get("/v1/payment/plans?region=US")
        assert usd.get_json()["currency"] == "USD"


# ── Phase B: Production JSAPI chain ────────────────────────

class TestProductionFlow:

    def test_wechat_order_jsapi_response_structure(self, prod_client):
        """JSAPI order response structure matches wx.requestPayment API."""
        # 1. WeChat login
        resp = prod_client.post("/v1/auth/wechat", json={"code": "prod_jsapi_001"})
        token = resp.get_json()["access_token"]

        mock_result = WeChatOrderResult(
            prepay_id="wx_prepay_miniprogram_001",
            out_trade_no="LOOMA20260714120000ABC12345",
            jsapi_package="prepay_id=wx_prepay_miniprogram_001",
            jsapi_pay_sign="MOCK_PAY_SIGN_BASE64",
            jsapi_nonce_str="mock_nonce_32_bytes_here_ok",
            jsapi_time_stamp="1700000000",
        )

        with patch(
            "src.payment.wechat_pay.create_jsapi_order",
            return_value=mock_result,
        ):
            resp = prod_client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "JSAPI"},
                headers=_auth_headers(token),
            )
            assert resp.status_code == 201
            data = resp.get_json()

        # wx.requestPayment expects: { timeStamp, nonceStr, package, signType, paySign }
        jsapi = data["jsapi_params"]
        assert jsapi["timeStamp"] == "1700000000"
        assert jsapi["nonceStr"] == "mock_nonce_32_bytes_here_ok"
        assert jsapi["package"] == "prepay_id=wx_prepay_miniprogram_001"
        assert jsapi["signType"] == "RSA"
        assert jsapi["paySign"] == "MOCK_PAY_SIGN_BASE64"

        assert data["order_id"]
        assert data["out_trade_no"]
        assert data["prepay_id"] == "wx_prepay_miniprogram_001"
        assert data["tier"] == "supporter"
        assert data["currency"] == "CNY"
        assert data["amount"] > 0

    def test_full_production_flow_with_notify(self, prod_client):
        """Production full chain: order → notify → refresh → profile."""
        # 1. WeChat login
        resp = prod_client.post("/v1/auth/wechat", json={"code": "prod_full_flow"})
        token = resp.get_json()["access_token"]
        user = resp.get_json()["user"]
        assert user["tier"] == "free"

        # 2. JSAPI order
        mock_result = WeChatOrderResult(
            prepay_id="wx_fullflow_prepay",
            out_trade_no="LOOMA_FULLFLOW_001",
            jsapi_package="prepay_id=wx_fullflow_prepay",
            jsapi_pay_sign="FULLFLOW_SIGN",
            jsapi_nonce_str="fullflow_nonce",
            jsapi_time_stamp="1700000100",
        )

        with patch(
            "src.payment.wechat_pay.create_jsapi_order",
            return_value=mock_result,
        ):
            resp = prod_client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "JSAPI"},
                headers=_auth_headers(token),
            )
            assert resp.status_code == 201
            order_data = resp.get_json()

        # 3. Mock WeChat pay notify (prod_app has WECHAT_API_V3_KEY → mock verify)
        notify_body = json.dumps({
            "id": "evt-fullflow",
            "create_time": "2026-07-14T10:00:00+08:00",
            "resource_type": "encrypt-resource",
            "event_type": "TRANSACTION.SUCCESS",
            "summary": "支付成功",
            "resource": {
                "out_trade_no": order_data["out_trade_no"],
                "transaction_id": "TXN_FULLFLOW",
                "trade_type": "JSAPI",
                "trade_state": "SUCCESS",
                "amount": {"total": 990, "currency": "CNY"},
            },
        })

        with patch(
            "src.api.routes.payment_routes.verify_notify_sign",
            return_value=True,
        ):
            resp = prod_client.post(
                "/v1/payment/wechat/notify",
                data=notify_body,
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert json.loads(resp.get_data(as_text=True))["code"] == "SUCCESS"

        # 4. Profile shows new tier (from DB)
        resp = prod_client.get("/v1/auth/profile", headers=_auth_headers(token))
        assert resp.get_json()["tier"] == "supporter"

        # 5. Refresh → new token with supporter tier
        resp = prod_client.post("/v1/auth/refresh", headers=_auth_headers(token))
        new_token = resp.get_json()["access_token"]
        secret = prod_client.application.config["JWT_SECRET"]
        claims = _decode_token(new_token, secret)
        assert claims["tier"] == "supporter"

        # 6. Payment status
        resp = prod_client.get("/v1/payment/status", headers=_auth_headers(new_token))
        status = resp.get_json()
        assert status["tier"] == "supporter"
        assert status["status"] == "active"
        assert status["expires_at"] is not None

        # 7. Order marked as paid
        db = prod_client.application._db
        order = db.get_order_by_out_trade_no(order_data["out_trade_no"])
        assert order["status"] == "paid"
        assert order["transaction_id"] == "TXN_FULLFLOW"
