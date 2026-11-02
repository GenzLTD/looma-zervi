"""认钱认人 join：principal_sub + 外部身份结算解析。"""

import pytest

from src.identity.ledger_subject import (
    AmbiguousLedgerSubject,
    ensure_principal_sub,
    resolve_settlement_user_id,
)


def _db(app, client):
    """app._db 由 before_request 懒初始化——先打一次请求。"""
    client.get("/health")
    return app._db


def test_ensure_principal_sub_bootstraps_to_user_id(app, client):
    db = _db(app, client)
    uid = db.create_user(email="join-a@test.com", password_hash="x")
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET principal_sub = NULL WHERE id = ?", (uid,))
    ps = ensure_principal_sub(db, uid)
    assert ps == uid
    user = db.get_user_by_id(uid)
    assert user["principal_sub"] == uid


def test_resolve_rejects_conflicting_session_and_wechat(app, client):
    """冲突应在 join 后失败（修复前：订单可挂 A、openid 属 B 仍可能下单）。"""
    db = _db(app, client)
    a = db.create_user(email="join-conflict-a@test.com", password_hash="x")
    b = db.create_user(email="join-conflict-b@test.com", password_hash="x")
    db.bind_wechat_to_user(b, "wx_openid_b_only")
    ensure_principal_sub(db, a)
    ensure_principal_sub(db, b)
    with pytest.raises(AmbiguousLedgerSubject):
        resolve_settlement_user_id(
            db,
            session_user_id=a,
            issuer="wechat",
            subject="wx_openid_b_only",
        )


def test_resolve_links_wechat_openid_to_same_user(app, client):
    db = _db(app, client)
    uid = db.create_user(email="join-wx@test.com", password_hash="x")
    db.bind_wechat_to_user(uid, "wx_openid_same")
    got = resolve_settlement_user_id(
        db,
        session_user_id=uid,
        issuer="wechat",
        subject="wx_openid_same",
    )
    assert got == uid


def test_stub_flow_settles_on_principal_sub(client, app):
    """注册 → stub 下码 → notify-simulate → tier 落在带 principal_sub 的同一人。"""
    resp = client.post("/v1/auth/register", json={
        "email": "join-stub@test.com",
        "password": "password123",
    })
    assert resp.status_code in (200, 201)
    body = resp.get_json()
    token = body["access_token"]
    user_id = body["user"]["id"]
    auth = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={"tier": "supporter"},
        headers=auth,
    )
    assert resp.status_code == 201
    out_trade_no = resp.get_json()["out_trade_no"]

    resp = client.post(
        "/v1/payment/wechat/notify-simulate",
        json={"out_trade_no": out_trade_no},
    )
    assert resp.status_code == 200
    assert resp.get_json()["tier"] == "supporter"

    resp = client.get("/v1/payment/status", headers=auth)
    assert resp.status_code == 200
    status = resp.get_json()
    assert status["tier"] == "supporter"
    assert status["principal_sub"] == user_id
    assert status["user_id"] == user_id

    db = app._db
    user = db.get_user_by_id(user_id)
    assert user["tier"] == "supporter"
    assert user["principal_sub"] == user_id


def test_stub_order_rejects_foreign_openid(client, app):
    """会话用户 A + 已绑定给 B 的 openid → 409 ambiguous_subject。"""
    db = _db(app, client)
    b = db.create_user(email="join-b-owner@test.com", password_hash="x")
    db.bind_wechat_to_user(b, "wx_owned_by_b")

    resp = client.post("/v1/auth/register", json={
        "email": "join-a-session@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={
            "tier": "supporter",
            "trade_type": "JSAPI",
            "openid": "wx_owned_by_b",
        },
        headers=auth,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "ambiguous_subject"