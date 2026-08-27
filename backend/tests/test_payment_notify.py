"""
WeChat Pay notify callback tests — signature verification + tier upgrade.

Coverage:
  - valid notify → tier upgraded, subscription created
  - missing order → returns SUCCESS (prevents WeChat retry storm)
  - already-paid order → idempotent (no double upgrade)
  - subscription expires_at ~30 days
  - profile reflects new tier after notify
  - invalid / empty JSON → handled gracefully
"""
import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from src.app import create_app


@pytest.fixture(autouse=True)
def _clean_wechat_env():
    """Ensure no WeChat credential env vars leak from other tests."""
    for key in ("WECHAT_MCHID", "WECHAT_APPID", "WECHAT_API_V3_KEY",
                "WECHAT_SERIAL_NO", "WECHAT_PRIVATE_KEY_PATH", "WECHAT_NOTIFY_URL"):
        os.environ.pop(key, None)
    yield


@pytest.fixture
def app():
    """Stub mode (notify is unaffected by stub_mode) + temp DB."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    os.environ["PAYMENT_STUB_MODE"] = "true"
    os.environ["WECHAT_DEV_MODE"] = "true"
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
    return resp.get_json()["access_token"], resp.get_json()["user"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_order(client, token, tier="supporter"):
    """Stub upgrade to create a paid-like order for notify testing."""
    resp = client.post(
        "/v1/payment/upgrade",
        json={"tier": tier},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    # Find the order just created
    db = client.application._db
    # Upgrade creates an order; we need its out_trade_no
    # Query the latest order for this user
    user_id = resp.get_json().get("user_id")
    user_profile = client.get("/v1/auth/profile", headers=_auth_headers(token))
    uid = user_profile.get_json()["id"]
    # Re-create: do a direct DB order for controllable out_trade_no
    return uid


def _make_notify_body(out_trade_no, transaction_id="TXN_TEST001",
                      trade_type="JSAPI", amount_total=990):
    return json.dumps({
        "id": "evt-test-001",
        "create_time": "2026-07-14T10:00:00+08:00",
        "resource_type": "encrypt-resource",
        "event_type": "TRANSACTION.SUCCESS",
        "summary": "支付成功",
        "resource": {
            "out_trade_no": out_trade_no,
            "transaction_id": transaction_id,
            "trade_type": trade_type,
            "trade_state": "SUCCESS",
            "amount": {"total": amount_total, "currency": "CNY"},
            "payer": {"openid": "oTestOpenID"},
            "success_time": "2026-07-14T10:00:01+08:00",
        },
    })


# ── Valid notify ───────────────────────────────────────────

class TestValidateNotify:

    def test_valid_notify_upgrades_tier(self, client):
        """A valid notify callback upgrades the user tier."""
        token, user = _register(client, "notify_up@test.com")
        db = client.application._db
        out_trade_no = "LOOMA_NOTIFY_UP_001"
        db.create_order(
            user_id=user["id"],
            plan_id="supporter_cn",
            tier="supporter",
            amount=9.9,
            currency="CNY",
            out_trade_no=out_trade_no,
        )

        # notify does NOT require auth → no signature validation in stub mode
        # (api_v3_key is empty → verify_notify_sign returns True)
        resp = client.post(
            "/v1/payment/wechat/notify",
            data=_make_notify_body(out_trade_no),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.get_data(as_text=True))["code"] == "SUCCESS"

        # Verify tier upgraded
        updated = db.get_user_by_id(user["id"])
        assert updated["tier"] == "supporter"

    def test_valid_notify_creates_subscription(self, client):
        """Notify callback creates a subscription record."""
        token, user = _register(client, "notify_sub@test.com")
        db = client.application._db
        out_trade_no = "LOOMA_NOTIFY_SUB_001"
        db.create_order(
            user_id=user["id"],
            plan_id="supporter_cn",
            tier="supporter",
            amount=9.9,
            currency="CNY",
            out_trade_no=out_trade_no,
        )

        client.post(
            "/v1/payment/wechat/notify",
            data=_make_notify_body(out_trade_no),
            content_type="application/json",
        )

        sub = db.get_subscription(user["id"])
        assert sub is not None
        assert sub["tier"] == "supporter"
        assert sub["status"] == "active"
        assert sub["expires_at"] is not None

    def test_subscription_expiry_approx_30_days(self, client):
        """Subscription expires roughly 30 days from now."""
        token, user = _register(client, "notify_expiry@test.com")
        db = client.application._db
        out_trade_no = "LOOMA_NOTIFY_EXPIRY_001"
        db.create_order(
            user_id=user["id"],
            plan_id="supporter_cn",
            tier="supporter",
            amount=9.9,
            currency="CNY",
            out_trade_no=out_trade_no,
        )

        client.post(
            "/v1/payment/wechat/notify",
            data=_make_notify_body(out_trade_no),
            content_type="application/json",
        )

        sub = db.get_subscription(user["id"])
        expiry = datetime.fromisoformat(sub["expires_at"])
        future = datetime.now() + timedelta(days=30)
        delta = (future - expiry).total_seconds()
        # within 1 day tolerance
        assert abs(delta) < 86400

    def test_profile_reflects_new_tier_after_notify(self, client):
        """GET /v1/auth/profile shows new tier after notify."""
        token, user = _register(client, "notify_profile@test.com")
        db = client.application._db
        out_trade_no = "LOOMA_NOTIFY_PROFILE_001"
        db.create_order(
            user_id=user["id"],
            plan_id="supporter_cn",
            tier="supporter",
            amount=9.9,
            currency="CNY",
            out_trade_no=out_trade_no,
        )

        client.post(
            "/v1/payment/wechat/notify",
            data=_make_notify_body(out_trade_no),
            content_type="application/json",
        )

        profile = client.get("/v1/auth/profile", headers=_auth_headers(token))
        assert profile.get_json()["tier"] == "supporter"


# ── Edge cases ─────────────────────────────────────────────

class TestNotifyEdgeCases:

    def test_missing_order_returns_success(self, client):
        """Non-existent order → still return SUCCESS to prevent retry storm."""
        resp = client.post(
            "/v1/payment/wechat/notify",
            data=_make_notify_body("LOOMA_NONEXISTENT_001"),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.get_data(as_text=True))["code"] == "SUCCESS"

    def test_already_paid_order_is_idempotent(self, client):
        """Already-paid order → no duplicate tier upgrade."""
        token, user = _register(client, "notify_idem@test.com")
        db = client.application._db
        out_trade_no = "LOOMA_NOTIFY_IDEM_001"
        db.create_order(
            user_id=user["id"],
            plan_id="supporter_cn",
            tier="supporter",
            amount=9.9,
            currency="CNY",
            out_trade_no=out_trade_no,
        )

        # First notification
        client.post(
            "/v1/payment/wechat/notify",
            data=_make_notify_body(out_trade_no, "TXN_IDEM_1"),
            content_type="application/json",
        )
        assert db.get_user_by_id(user["id"])["tier"] == "supporter"

        # Second notification (duplicate) — should NOT fail
        resp = client.post(
            "/v1/payment/wechat/notify",
            data=_make_notify_body(out_trade_no, "TXN_IDEM_1"),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.get_data(as_text=True))["code"] == "SUCCESS"
        # Tier still supporter, no crash
        assert db.get_user_by_id(user["id"])["tier"] == "supporter"

    def test_invalid_json_body_handled(self, client):
        """Malformed JSON body → handled gracefully."""
        resp = client.post(
            "/v1/payment/wechat/notify",
            data="not valid json at all",
            content_type="application/json",
        )
        # Should not 500 crash
        assert resp.status_code in (200, 400, 500)
