"""通道 B 内容信号 ingest —— 签名校验 + publisher 身份断言 + 幂等。

对齐三方归集对账文档 §5.1 验证用例：
  9.  用乙的密钥签一条 data.publisher_id=甲 的信号 → 必须拒绝（核心断言）
  10. 重放同 nonce → 200 且不重复处理
  11. 错签名的信号 → 401
"""
import hashlib
import hmac
import json
import uuid

import pytest

MASTER = "test-signal-master"


def _derive(publisher_id: str) -> bytes:
    return hmac.new(MASTER.encode(), f"signal:{publisher_id}".encode(),
                    hashlib.sha256).digest()


def _sign_envelope(envelope: dict, publisher_id: str) -> tuple[str, str, dict]:
    """返回 (signature, raw_body, headers)。签名覆盖发送的原始字节。"""
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    sig = hmac.new(_derive(publisher_id), body.encode(), hashlib.sha256).hexdigest()
    return sig, body, {"X-Signal-Signature": sig, "Content-Type": "application/json"}


def _make_driver(app, prefix) -> str:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@test.local"
    app._db.create_user(email=email, password_hash="x", name=prefix)
    with app._db.get_conn() as conn:
        conn.execute("UPDATE users SET role='driver' WHERE email=?", (email,))
    return app._db.get_user_by_email(email)["id"]


@pytest.fixture
def sig_client(client, app):
    client.get("/v1/poetry/stats")  # 触发 before_request → app._db 懒加载
    app.config["SIGNAL_BRIDGE_SECRET"] = MASTER
    return client, app


def test_valid_publish_is_accepted_and_landed(sig_client):
    client, app = sig_client
    drv = _make_driver(app, "pub-a")
    env = {"signal_type": "content_publish", "publisher_id": drv,
           "nonce": str(uuid.uuid4()),
           "data": {"slug": "poem-1", "title": "静夜思", "content": "床前明月光"}}
    sig, body, headers = _sign_envelope(env, drv)
    resp = client.post("/v1/signals/content", data=body, headers=headers)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    art = resp.get_json()["article"]
    assert art["driver_id"] == drv and art["slug"] == "poem-1"
    # 落库可查（稳定键 (publisher, slug)）
    assert app._db.get_article_by_slug(drv, "poem-1") is not None


def test_replay_same_nonce_is_duplicate(sig_client):
    client, app = sig_client
    drv = _make_driver(app, "pub-a")
    env = {"signal_type": "content_publish", "publisher_id": drv,
           "nonce": "fixed-nonce-001",
           "data": {"slug": "poem-2", "title": "t", "content": "c"}}
    sig, body, headers = _sign_envelope(env, drv)
    assert client.post("/v1/signals/content", data=body, headers=headers).status_code == 201
    resp = client.post("/v1/signals/content", data=body, headers=headers)
    assert resp.status_code == 200 and resp.get_json()["status"] == "duplicate"
    # 不重复处理
    arts = app._db.list_articles(driver_id=drv)
    assert len([a for a in arts if a["slug"] == "poem-2"]) == 1


def test_publisher_b_key_signing_a_claim_must_fail(sig_client):
    """核心断言（用例 9）：乙的密钥 + 甲的 publisher_id → 401。"""
    client, app = sig_client
    drv_a = _make_driver(app, "pub-a")
    drv_b = _make_driver(app, "pub-b")
    env = {"signal_type": "content_publish", "publisher_id": drv_a,  # 冒名甲
           "nonce": str(uuid.uuid4()),
           "data": {"slug": "evil", "title": "乙的内容", "content": "x"}}
    # 用乙的密钥签名
    sig, body, headers = _sign_envelope(env, drv_b)
    resp = client.post("/v1/signals/content", data=body, headers=headers)
    assert resp.status_code == 401
    # 甲名下没有任何内容落地
    assert app._db.get_article_by_slug(drv_a, "evil") is None
    assert app._db.get_article_by_slug(drv_b, "evil") is None


def test_bad_signature_is_401(sig_client):
    """错签名的信号 → 401（不泄露原因）。"""
    client, app = sig_client
    drv = _make_driver(app, "pub-a")
    env = {"signal_type": "content_publish", "publisher_id": drv,
           "nonce": str(uuid.uuid4()),
           "data": {"slug": "s", "title": "t", "content": "c"}}
    _, body, _ = _sign_envelope(env, drv)
    resp = client.post("/v1/signals/content", data=body,
                       headers={"X-Signal-Signature": "deadbeef",
                                "Content-Type": "application/json"})
    assert resp.status_code == 401
    assert b"reason" not in resp.data.lower()
    assert app._db.get_article_by_slug(drv, "s") is None


def test_inner_publisher_mismatch_is_403(sig_client):
    client, app = sig_client
    drv_a = _make_driver(app, "pub-a")
    drv_b = _make_driver(app, "pub-b")
    env = {"signal_type": "content_publish", "publisher_id": drv_a,
           "nonce": str(uuid.uuid4()),
           "data": {"publisher_id": drv_b,  # 信封甲、载荷乙 → 断言拦截
                    "slug": "mismatch", "title": "t", "content": "c"}}
    sig, body, headers = _sign_envelope(env, drv_a)
    resp = client.post("/v1/signals/content", data=body, headers=headers)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_unknown_publisher_is_403(sig_client):
    client, _ = sig_client
    ghost = "no-such-driver-id"
    env = {"signal_type": "content_publish", "publisher_id": ghost,
           "nonce": str(uuid.uuid4()),
           "data": {"slug": "x", "title": "t", "content": "c"}}
    sig, body, headers = _sign_envelope(env, ghost)
    resp = client.post("/v1/signals/content", data=body, headers=headers)
    assert resp.status_code == 403


def test_content_remove_is_idempotent(sig_client):
    client, app = sig_client
    drv = _make_driver(app, "pub-a")
    app._db.create_article(driver_id=drv, title="t", slug="bye", content="c")
    env = {"signal_type": "content_remove", "publisher_id": drv,
           "nonce": str(uuid.uuid4()), "data": {"slug": "bye"}}
    sig, body, headers = _sign_envelope(env, drv)
    resp = client.post("/v1/signals/content", data=body, headers=headers)
    assert resp.status_code == 200 and resp.get_json()["removed"] is True
    # 再删：幂等成功但 removed=False
    env2 = dict(env, nonce=str(uuid.uuid4()))
    sig2, body2, headers2 = _sign_envelope(env2, drv)
    resp = client.post("/v1/signals/content", data=body2, headers=headers2)
    assert resp.status_code == 200 and resp.get_json()["removed"] is False


def test_signal_layer_disabled_without_secret(client, app):
    app.config["SIGNAL_BRIDGE_SECRET"] = ""
    resp = client.post("/v1/signals/content",
                       json={"signal_type": "content_publish",
                             "publisher_id": "x", "nonce": "n", "data": {}})
    assert resp.status_code == 503
