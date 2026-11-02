"""Hang-list authz batch: funnel / seed-demo / wechat notify / auth bridge."""
import json
import os

import pytest


def _register(client, email, password="test-pass-123"):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "name": "Hang"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    return body["access_token"], body["user"]


def _promote_admin(client, email: str) -> None:
    with client.application._db.get_conn() as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))


def test_funnel_admin_ok(client):
    token, user = _register(client, "hang-funnel-admin@test.local")
    _promote_admin(client, user["email"])
    token = client.post(
        "/v1/auth/login",
        json={"email": user["email"], "password": "test-pass-123"},
    ).get_json()["access_token"]
    resp = client.get(
        "/v1/analytics/funnel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "steps" in resp.get_json()


def test_funnel_free_403(client):
    token, _ = _register(client, "hang-funnel-free@test.local")
    resp = client.get(
        "/v1/analytics/funnel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_seed_demo_allowed_in_non_production(client, app):
    """conftest uses WECHAT_DEV_MODE + default FLASK_ENV=development -> allowed."""
    token, _ = _register(client, "hang-seed-dev@test.local")
    assert (app.config.get("FLASK_ENV") or "").lower() != "production"
    resp = client.post(
        "/v1/jobs/seed-demo",
        headers={"Authorization": f"Bearer {token}"},
        json={"jobs": [{"id": "HANG-SEED-1", "title": "Hang Job"}]},
    )
    assert resp.status_code == 200
    assert "HANG-SEED-1" in resp.get_json()["created"]


def test_seed_demo_production_free_403(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "FLASK_ENV", "production")
    monkeypatch.setitem(app.config, "TESTING", False)
    token, _ = _register(client, "hang-seed-prod-free@test.local")
    resp = client.post(
        "/v1/jobs/seed-demo",
        headers={"Authorization": f"Bearer {token}"},
        json={"jobs": [{"id": "HANG-SEED-BLOCK", "title": "No"}]},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_seed_demo_production_admin_ok(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "FLASK_ENV", "production")
    monkeypatch.setitem(app.config, "TESTING", False)
    token, user = _register(client, "hang-seed-prod-admin@test.local")
    _promote_admin(client, user["email"])
    token = client.post(
        "/v1/auth/login",
        json={"email": user["email"], "password": "test-pass-123"},
    ).get_json()["access_token"]
    resp = client.post(
        "/v1/jobs/seed-demo",
        headers={"Authorization": f"Bearer {token}"},
        json={"jobs": [{"id": "HANG-SEED-ADMIN", "title": "Admin Job"}]},
    )
    assert resp.status_code == 200
    assert "HANG-SEED-ADMIN" in resp.get_json()["created"]


def test_wechat_notify_empty_body_400(client):
    resp = client.post(
        "/v1/payment/wechat/notify",
        data="",
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = json.loads(resp.get_data(as_text=True))
    assert body["code"] == "FAIL"
    assert "empty" in body["message"].lower()


def test_wechat_notify_unsigned_with_key_401(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "WECHAT_API_V3_KEY", "test-api-v3-key-32bytes-long!!")
    resp = client.post(
        "/v1/payment/wechat/notify",
        data=json.dumps({"event_type": "TRANSACTION.SUCCESS", "resource": {}}),
        content_type="application/json",
    )
    assert resp.status_code == 401
    body = json.loads(resp.get_data(as_text=True))
    assert body["code"] == "FAIL"


def test_wechat_notify_invalid_json_400_not_500(client):
    resp = client.post(
        "/v1/payment/wechat/notify",
        data="not valid json",
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = json.loads(resp.get_data(as_text=True))
    assert body["code"] == "FAIL"


def test_bridge_supabase_still_501(client):
    resp = client.post("/v1/auth/bridge", json={})
    assert resp.status_code == 501
    assert resp.get_json()["error"] == "not_implemented"


def test_bridge_circle_without_secret_501(client, monkeypatch):
    monkeypatch.delenv("ETHOS_AUTH_SECRET", raising=False)
    monkeypatch.setitem(client.application.config, "ETHOS_AUTH_SECRET", "")
    token, _ = _register(client, "hang-bridge-nosec@test.local")
    resp = client.post(
        "/v1/auth/bridge",
        json={"target": "circle"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 501
    body = resp.get_json()
    assert body["error"] == "not_implemented"
    assert body.get("design", {}).get("target") == "circle"


def test_bridge_circle_with_secret_mints_token(client, monkeypatch):
    secret = "hang-ethos-secret-for-bridge-tests!!"
    monkeypatch.setenv("ETHOS_AUTH_SECRET", secret)
    monkeypatch.setitem(client.application.config, "ETHOS_AUTH_SECRET", secret)
    token, user = _register(client, "hang-bridge-ok@test.local")
    resp = client.post(
        "/v1/auth/bridge",
        json={"target": "circle"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["target"] == "circle"
    assert body["circle_token"].count(".") == 2
    assert body["user_id"] == user["id"]
    assert body["sub"]