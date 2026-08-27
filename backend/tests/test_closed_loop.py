"""Tests for referral profile share and enterprise import closed-loop."""
import json
import tempfile
import os
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
    resp = client.post("/v1/auth/register", json={"email": email, "password": "secret123", "name": "Test"})
    assert resp.status_code == 201
    return resp.get_json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _upgrade_tier(client, token, tier="supporter"):
    resp = client.post(
        "/v1/payment/upgrade",
        json={"tier": tier},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    return resp.get_json().get("access_token") or token


def test_profile_share_view_and_import(client):
    """Closed loop: seeker syncs profile → share code → HR views → HR imports."""
    seeker_token = _register(client, "seeker@test.com")
    hr_token = _register(client, "hr@test.com")
    hr_token = _upgrade_tier(client, hr_token, "supporter")

    personality = {
        "name": "星云艺术家",
        "emoji": "🎨",
        "tagline": "创造力 + 感染力",
        "desc": "测试描述",
        "traits": ["创造力爆表"],
    }

    sync_resp = client.post(
        "/v1/game/profile-sync",
        headers=_auth_headers(seeker_token),
        json={
            "personality_type": personality["name"],
            "personality_detail": json.dumps(personality, ensure_ascii=False),
        },
    )
    assert sync_resp.status_code == 200

    create_resp = client.post(
        "/v1/referral/create",
        headers=_auth_headers(seeker_token),
        json={"purpose": "profile_share"},
    )
    assert create_resp.status_code in (200, 201)
    code = create_resp.get_json()["code"]

    view_resp = client.get(f"/v1/referral/profile-view/{code}")
    assert view_resp.status_code == 200
    view = view_resp.get_json()
    assert view["personality_type"] == "星云艺术家"
    assert view["personality_detail"]["emoji"] == "🎨"
    assert "timeline_l1" in view
    assert view["timeline_l1"]["level"] == "l1"
    assert "message" in view["timeline_l1"]
    assert "has_thickness" in view["timeline_l1"]

    ent_resp = client.post(
        "/v1/enterprise/create",
        headers=_auth_headers(hr_token),
        json={"name": "测试企业"},
    )
    assert ent_resp.status_code == 201

    import_resp = client.post(
        "/v1/enterprise/candidates/import-share",
        headers=_auth_headers(hr_token),
        json={"share_code": code},
    )
    assert import_resp.status_code == 201
    imported = import_resp.get_json()
    assert imported["imported"] is True
    assert imported["name"]

    list_resp = client.get("/v1/enterprise/candidates", headers=_auth_headers(hr_token))
    assert list_resp.status_code == 200
    candidates = list_resp.get_json()["candidates"]
    assert len(candidates) == 1

    detail_resp = client.get(
        f"/v1/enterprise/candidate/{candidates[0]['id']}",
        headers=_auth_headers(hr_token),
    )
    assert detail_resp.status_code == 200
    assert detail_resp.get_json()["profile_data"]["personality_type"] == "星云艺术家"


def test_referral_use_rejects_profile_share_code(client):
    seeker_token = _register(client, "s2@test.com")
    user_token = _register(client, "u2@test.com")

    create_resp = client.post(
        "/v1/referral/create",
        headers=_auth_headers(seeker_token),
        json={"purpose": "profile_share"},
    )
    code = create_resp.get_json()["code"]

    use_resp = client.post(
        "/v1/referral/use",
        headers=_auth_headers(user_token),
        json={"code": code},
    )
    assert use_resp.status_code == 400


def test_game_profile_returns_mission_ids(client):
    token = _register(client, "g1@test.com")

    complete_resp = client.post(
        "/v1/game/mission-complete",
        headers=_auth_headers(token),
        json={"mission_id": "personality", "xp_reward": 50},
    )
    assert complete_resp.status_code == 200
    complete_data = complete_resp.get_json()
    # total_xp must equal actual profile xp, not double-count the reward
    assert complete_data["xp_earned"] == 50
    assert complete_data["total_xp"] == 50
    assert complete_data["level"] == 1

    profile_resp = client.get("/v1/game/profile", headers=_auth_headers(token))
    assert profile_resp.status_code == 200
    data = profile_resp.get_json()
    assert data["missions_completed"] == ["personality"]
    assert data["xp"] == 50
    assert data["level"] == 1


def test_credit_check_requires_consent_then_succeeds(client):
    """Compliance + closed-loop: credit_query consent gate on check-company."""
    token = _register(client, "credit@test.com")

    denied = client.post(
        "/v1/credit/check-company",
        headers=_auth_headers(token),
        json={"company_name": "测试科技"},
    )
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "consent_required"

    grant = client.post(
        "/v1/compliance/consent/grant",
        headers=_auth_headers(token),
        json={"scope": "credit_query"},
    )
    assert grant.status_code == 200

    ok = client.post(
        "/v1/credit/check-company",
        headers=_auth_headers(token),
        json={"company_name": "测试科技"},
    )
    # 200 when LLM available; 422 when LLM/key unavailable (consent gate already passed)
    assert ok.status_code in (200, 422)
    if ok.status_code == 200:
        assert ok.get_json().get("warning")
