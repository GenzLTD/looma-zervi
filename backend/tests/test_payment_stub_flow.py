"""Stub-mode WeChat order simulation E2E — 商户号审批前的本机全链验证。

覆盖：下码（模拟二维码）→ 模拟回调核销 → 订阅生效 → 幂等防护。
走的是与生产完全一致的核销链 _process_payment_completed。
"""


def test_stub_wechat_order_flow(client):
    """注册 → stub 下码 → notify-simulate → tier/订阅生效。"""
    resp = client.post("/v1/auth/register", json={
        "email": "stub-order@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # 1. stub 下码：返回 201 + 模拟二维码 + 契约价（¥29）
    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={"tier": "supporter"},
        headers=auth,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["stub_mode"] is True
    assert data["amount"] == 29
    assert data["currency"] == "CNY"
    assert data["qr_code_url"].startswith("weixin://wxpay/stub/")
    out_trade_no = data["out_trade_no"]

    # 2. 模拟微信回调：走共享核销链
    resp = client.post(
        "/v1/payment/wechat/notify-simulate",
        json={"out_trade_no": out_trade_no},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["settled"] is True
    assert body["tier"] == "supporter"
    assert body["amount"] == 29

    # 3. 状态：supporter / active / +30 天
    resp = client.get("/v1/payment/status", headers=auth)
    assert resp.status_code == 200
    status = resp.get_json()
    assert status["tier"] == "supporter"
    assert status["status"] == "active"
    assert status["expires_at"] is not None


def test_stub_notify_simulate_is_idempotent(client):
    """重复模拟回调不得二次核销（幂等）。"""
    resp = client.post("/v1/auth/register", json={
        "email": "stub-idem@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={"tier": "pro"},
        headers=auth,
    )
    out_trade_no = resp.get_json()["out_trade_no"]

    first = client.post(
        "/v1/payment/wechat/notify-simulate",
        json={"out_trade_no": out_trade_no},
    )
    assert first.status_code == 200

    second = client.post(
        "/v1/payment/wechat/notify-simulate",
        json={"out_trade_no": out_trade_no},
    )
    assert second.status_code == 409
    assert second.get_json()["error"] == "not_settled"


def test_stub_order_rejects_downgrade(client):
    """stub 下码同样受 tier 降级保护。"""
    resp = client.post("/v1/auth/register", json={
        "email": "stub-downgrade@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # 先升到 pro
    client.post(
        "/v1/payment/upgrade?region=CN",
        json={"tier": "pro"},
        headers=auth,
    )
    # 再下 supporter 单 → 拒绝
    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={"tier": "supporter"},
        headers=auth,
    )
    assert resp.status_code == 400


def test_notify_simulate_requires_stub_mode(app):
    """非 stub 模式下模拟回调必须 403（生产安全闸）。"""
    app.config["PAYMENT_STUB_MODE"] = False
    resp = app.test_client().post(
        "/v1/payment/wechat/notify-simulate",
        json={"out_trade_no": "LOOMAX"},
    )
    assert resp.status_code == 403


def test_stub_jsapi_order_returns_mock_params(client):
    """小程序 JSAPI 下码：stub 返回与生产同形状的 jsapi_params（wx.requestPayment 可直连）。"""
    resp = client.post("/v1/auth/register", json={
        "email": "stub-jsapi@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={"tier": "supporter", "trade_type": "JSAPI", "openid": "dev_e2e"},
        headers=auth,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    params = data["jsapi_params"]
    assert set(params) == {"appId", "timeStamp", "nonceStr", "package", "signType", "paySign"}
    assert params["package"].startswith("prepay_id=stub_")
    assert data["prepay_id"].startswith("stub_")
