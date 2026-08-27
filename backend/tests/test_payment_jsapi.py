"""
JSAPI openid auto-fill + WeChat Pay order creation tests.

Coverage:
  - openid required when user has none (no DB record, no explicit param)
  - auto-fill openid from DB wechat_openid
  - explicit openid passes validation
  - mock JSAPI order returns correct jsapi_params structure
  - order persisted to DB
  - openid passed through to wechat API correctly
  - NATIVE mode unaffected by openid requirement
  - downgrade / same-tier / invalid-tier rejection
  - unauthenticated → 401
"""
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.app import create_app
from src.payment.wechat_pay import WeChatOrderResult

# create_jsapi_order is locally imported → patch at source module
MOCK_JSAPI_PATH = "src.payment.wechat_pay.create_jsapi_order"
# create_native_order is module-level imported → patch in payment_routes
MOCK_NATIVE_PATH = "src.api.routes.payment_routes.create_native_order"


@pytest.fixture
def app():
    """Stub_mode=false + temp DB + fake credentials to pass credential check."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    os.environ["PAYMENT_STUB_MODE"] = "false"
    os.environ["WECHAT_MCHID"] = "1234567890"
    os.environ["WECHAT_APPID"] = "wx_test_appid"
    os.environ["WECHAT_API_V3_KEY"] = "32byteslongsecretkeyforwechatpay"
    os.environ["WECHAT_SERIAL_NO"] = "TEST_SERIAL_NO"
    os.environ["WECHAT_PRIVATE_KEY_PATH"] = ""
    os.environ["WECHAT_NOTIFY_URL"] = "https://test.example.com/notify"
    os.environ["WECHAT_DEV_MODE"] = "true"
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


def _mock_jsapi_result():
    return WeChatOrderResult(
        prepay_id="wx_mock_prepay_001",
        out_trade_no="mock_oid",
        jsapi_package="prepay_id=wx_mock_prepay_001",
        jsapi_pay_sign="MOCK_SIGN_BASE64",
        jsapi_nonce_str="mock_nonce_32_bytes_here_ok",
        jsapi_time_stamp="1700000000",
    )


# ── openid requirement ────────────────────────────────────

class TestOpenidValidation:

    def test_jsapi_no_openid_no_db_record_returns_400(self, client):
        """User registered by email → no wechat_openid → JSAPI rejected 400."""
        token, _ = _register(client, "no_openid@test.com")
        resp = client.post(
            "/v1/payment/wechat/order",
            json={"tier": "supporter", "trade_type": "JSAPI"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "openid_required"

    def test_jsapi_openid_auto_filled_from_db(self, client):
        """User with wechat_openid in DB → auto-filled, check passes."""
        # register via wechat (dev mode puts openid in DB)
        resp = client.post("/v1/auth/wechat", json={"code": "auto_fill_test_001"})
        token = resp.get_json()["access_token"]

        with patch(MOCK_JSAPI_PATH, return_value=_mock_jsapi_result()):
            resp = client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "JSAPI"},
                headers=_auth_headers(token),
            )
            # Should not be openid_required
            assert resp.status_code == 201

    def test_jsapi_explicit_openid_passes(self, client):
        """Explicit openid provided → validation passes."""
        token, _ = _register(client, "explicit_oid@test.com")
        with patch(MOCK_JSAPI_PATH, return_value=_mock_jsapi_result()):
            resp = client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "JSAPI", "openid": "explicit_oid_123"},
                headers=_auth_headers(token),
            )
            assert resp.status_code == 201


# ── JSAPI order creation ───────────────────────────────────

class TestJSAPIOrderCreation:

    def test_jsapi_order_returns_correct_structure(self, client):
        """Mock JSAPI returns full jsapi_params for wx.requestPayment."""
        token, _ = _register(client, "jsapi_structure@test.com")
        mock = WeChatOrderResult(
            prepay_id="wx_prepay_structure",
            out_trade_no="LOOMA_STRUCTURE",
            jsapi_package="prepay_id=wx_prepay_structure",
            jsapi_pay_sign="STRUCTURE_SIGN",
            jsapi_nonce_str="structure_nonce",
            jsapi_time_stamp="1700000100",
        )
        with patch(MOCK_JSAPI_PATH, return_value=mock):
            resp = client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "JSAPI", "openid": "structure_oid"},
                headers=_auth_headers(token),
            )
            assert resp.status_code == 201
            data = resp.get_json()
            jsapi = data["jsapi_params"]
            assert jsapi["appId"] == "wx_test_appid"
            assert jsapi["timeStamp"] == "1700000100"
            assert jsapi["nonceStr"] == "structure_nonce"
            assert jsapi["package"] == "prepay_id=wx_prepay_structure"
            assert jsapi["signType"] == "RSA"
            assert jsapi["paySign"] == "STRUCTURE_SIGN"
            assert data["prepay_id"] == "wx_prepay_structure"
            assert data["tier"] == "supporter"
            assert data["currency"] == "CNY"
            assert data["amount"] > 0

    def test_jsapi_order_persisted_in_db(self, client):
        """Order is written to orders table after creation."""
        token, _ = _register(client, "jsapi_db@test.com")
        with patch(MOCK_JSAPI_PATH, return_value=_mock_jsapi_result()):
            resp = client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "JSAPI", "openid": "db_oid"},
                headers=_auth_headers(token),
            )
        assert resp.status_code == 201
        out_trade_no = resp.get_json()["out_trade_no"]
        db = client.application._db
        order = db.get_order_by_out_trade_no(out_trade_no)
        assert order is not None
        assert order["status"] == "pending"
        assert order["tier"] == "supporter"

    def test_jsapi_openid_passed_to_wechat_api(self, client):
        """Verify the openid reaches create_jsapi_order call."""
        token, _ = _register(client, "jsapi_oid_pass@test.com")
        with patch(MOCK_JSAPI_PATH) as mock_create:
            mock_create.return_value = _mock_jsapi_result()
            client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "JSAPI", "openid": "verify_this_oid"},
                headers=_auth_headers(token),
            )
            mock_create.assert_called_once()
            kwargs = mock_create.call_args.kwargs
            assert kwargs["openid"] == "verify_this_oid"


# ── NATIVE mode ────────────────────────────────────────────

class TestNativeMode:

    def test_native_unaffected_by_openid(self, client):
        """NATIVE mode should NOT require openid."""
        token, _ = _register(client, "native_no_oid@test.com")
        mock = WeChatOrderResult(
            prepay_id="",
            out_trade_no="LOOMA_NATIVE",
            qr_code_url="weixin://wxpay/bizpayurl?pr=native_mock",
        )
        with patch(MOCK_NATIVE_PATH, return_value=mock):
            resp = client.post(
                "/v1/payment/wechat/order",
                json={"tier": "supporter", "trade_type": "NATIVE"},
                headers=_auth_headers(token),
            )
            assert resp.status_code == 201
            assert resp.get_json()["qr_code_url"]


# ── Edge cases ─────────────────────────────────────────────

class TestEdgeCases:

    def test_jsapi_cannot_downgrade(self, client):
        """Upgraded user cannot downgrade via new payment."""
        token, user = _register(client, "down@test.com")
        db = client.application._db
        db.update_user_tier(user["id"], "pro")

        resp = client.post(
            "/v1/payment/wechat/order",
            json={"tier": "supporter", "trade_type": "JSAPI", "openid": "test_oid"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400
        assert "downgrade" in resp.get_json()["message"].lower()

    def test_same_tier_rejected(self, client):
        """Cannot place order for current tier."""
        token, user = _register(client, "same@test.com")
        db = client.application._db
        db.update_user_tier(user["id"], "supporter")

        resp = client.post(
            "/v1/payment/wechat/order",
            json={"tier": "supporter", "trade_type": "JSAPI", "openid": "test_oid"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400

    def test_invalid_tier(self, client):
        token, _ = _register(client, "invalid_tier@test.com")
        resp = client.post(
            "/v1/payment/wechat/order",
            json={"tier": "enterprise", "trade_type": "JSAPI", "openid": "test_oid"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400

    def test_unauthenticated(self, client):
        resp = client.post(
            "/v1/payment/wechat/order",
            json={"tier": "supporter", "trade_type": "JSAPI"},
        )
        assert resp.status_code == 401
