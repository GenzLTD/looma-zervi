"""Timeline phase-1: schema, quiz dual-write, API, idempotent backfill."""
import json
import os
import tempfile

import pytest

from src.app import create_app


@pytest.fixture
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret"
    application = create_app("testing")
    yield application
    os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, email):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "secret123", "name": "Timeline"},
    )
    assert resp.status_code == 201
    return resp.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_profile_sync_writes_timeline_hypothesis(client):
    token = _register(client, "tl_seeker@test.com")
    sync = client.post(
        "/v1/game/profile-sync",
        headers=_auth(token),
        json={
            "personality_type": "超新星领航员",
            "personality_detail": json.dumps({"tagline": "test"}, ensure_ascii=False),
        },
    )
    assert sync.status_code == 200

    listing = client.get("/v1/timeline", headers=_auth(token))
    assert listing.status_code == 200
    body = listing.get_json()
    kinds = {item["event_kind"] for item in body["items"]}
    assert "quiz_completed" in kinds
    assert "initial_hypothesis" in kinds
    hypo = next(i for i in body["items"] if i["event_kind"] == "initial_hypothesis")
    assert hypo["weight_role"] == "hypothesis"
    assert hypo["payload"].get("label") == "initial_hypothesis"
    assert "冷启动" not in hypo["title"]
    quiz = next(i for i in body["items"] if i["event_kind"] == "quiz_completed")
    assert quiz["title"] == "完成职业画像初测"


def test_timeline_idempotent_on_resync_and_backfill(client):
    token = _register(client, "tl_idem@test.com")
    payload = {
        "personality_type": "星云艺术家",
        "personality_detail": "{}",
    }
    for _ in range(2):
        assert client.post(
            "/v1/game/profile-sync", headers=_auth(token), json=payload
        ).status_code == 200

    bf = client.post("/v1/timeline/bridge/backfill", headers=_auth(token))
    assert bf.status_code == 200

    listing = client.get("/v1/timeline", headers=_auth(token))
    items = listing.get_json()["items"]
    quiz_rows = [i for i in items if i["event_kind"] == "quiz_completed"]
    hypo_rows = [i for i in items if i["event_kind"] == "initial_hypothesis"]
    assert len(quiz_rows) == 1
    assert len(hypo_rows) == 1


def test_manual_check_in_and_growth_low_confidence(client):
    token = _register(client, "tl_checkin@test.com")
    create = client.post(
        "/v1/timeline/events",
        headers=_auth(token),
        json={
            "event_kind": "check_in",
            "title": "本周签到",
            "payload": {"mood": "focused", "focus": "找工作"},
        },
    )
    assert create.status_code == 201
    assert create.get_json()["event_kind"] == "check_in"

    # system kinds rejected
    bad = client.post(
        "/v1/timeline/events",
        headers=_auth(token),
        json={"event_kind": "initial_hypothesis", "title": "hack"},
    )
    assert bad.status_code == 400

    growth = client.get("/v1/timeline/growth", headers=_auth(token))
    assert growth.status_code == 200
    gbody = growth.get_json()
    assert gbody["confidence"] == "low"
    assert gbody["event_count"] >= 1
    assert "本周记录" in gbody["message"] or "项目" in gbody["message"]
    dims = {d["id"]: d for d in gbody["dimensions"]}
    assert dims["action_density"]["max"] == 5
    assert "满分" in dims["action_density"]["hint"]
    assert dims["exploration"]["max"] == 5
    assert dims["expression"]["max"] == 5


def test_soft_delete_hides_from_list(client):
    token = _register(client, "tl_del@test.com")
    create = client.post(
        "/v1/timeline/events",
        headers=_auth(token),
        json={"event_kind": "project_record", "title": "某项目", "summary": "上线"},
    )
    eid = create.get_json()["id"]
    deleted = client.delete(f"/v1/timeline/events/{eid}", headers=_auth(token))
    assert deleted.status_code == 200
    listing = client.get("/v1/timeline", headers=_auth(token))
    ids = {i["id"] for i in listing.get_json()["items"]}
    assert eid not in ids


def test_share_authorized_from_referral_profile_share(client):
    token = _register(client, "tl_share@test.com")
    create = client.post(
        "/v1/referral/create",
        headers=_auth(token),
        json={"purpose": "profile_share"},
    )
    assert create.status_code in (200, 201)

    listing = client.get("/v1/timeline", headers=_auth(token))
    kinds = {i["event_kind"] for i in listing.get_json()["items"]}
    assert "share_authorized" in kinds


def test_trust_share_code_writes_timeline(client):
    token = _register(client, "tl_trust_sc@test.com")
    resp = client.post(
        "/v1/trust/share-code",
        headers=_auth(token),
        json={"scope": ["identity"]},
    )
    assert resp.status_code == 201
    listing = client.get("/v1/timeline", headers=_auth(token))
    items = [i for i in listing.get_json()["items"] if i["event_kind"] == "share_authorized"]
    assert items
    assert items[0]["payload"].get("channel") == "trust_verify"


def test_profile_view_timeline_l1_empty_and_with_checkin(client):
    """Share page exposes L1 summary; empty stays honest; check_in adds thickness."""
    token = _register(client, "tl_l1@test.com")
    # quiz only → thin (no behaviour thickness yet)
    assert client.post(
        "/v1/game/profile-sync",
        headers=_auth(token),
        json={"personality_type": "超新星领航员", "personality_detail": "{}"},
    ).status_code == 200
    share = client.post(
        "/v1/referral/create",
        headers=_auth(token),
        json={"purpose": "profile_share"},
    )
    assert share.status_code in (200, 201)
    code = share.get_json()["code"]
    view = client.get(f"/v1/referral/profile-view/{code}").get_json()
    l1 = view["timeline_l1"]
    assert l1["has_thickness"] is False
    assert l1["confidence"] in ("thin", "empty", "building")
    assert "不足" in l1["message"] or "假设" in l1["message"]

    # add check_in → thickness
    assert client.post(
        "/v1/timeline/events",
        headers=_auth(token),
        json={"event_kind": "check_in", "title": "签到", "payload": {"mood": "focused"}},
    ).status_code == 201
    view2 = client.get(f"/v1/referral/profile-view/{code}").get_json()
    l1b = view2["timeline_l1"]
    assert l1b["has_thickness"] is True
    assert l1b["check_in_count"] >= 1
