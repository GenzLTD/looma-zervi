"""Tests for product analytics and closed-loop funnel stats."""
import json


def _register(client, email="analytics@test.local"):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "test-pass-123", "name": "Analytics"},
    )
    assert resp.status_code == 201
    return resp.get_json()["access_token"]


def _promote_admin(client, email: str) -> None:
    with client.application._db.get_conn() as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))


def test_funnel_free_user_forbidden(client):
    """Free (non-admin) JWT must not read global funnel aggregates."""
    token = _register(client, "funnel-free@test.local")
    resp = client.get(
        "/v1/analytics/funnel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_funnel_unauthenticated_rejected(client):
    resp = client.get("/v1/analytics/funnel")
    assert resp.status_code == 401


def test_log_events_batch(client):
    token = _register(client, "batch@test.local")
    resp = client.post(
        "/v1/analytics/events",
        json={
            "events": [
                {
                    "event_name": "share_link_copied",
                    "session_id": "sess-1",
                    "platform": "planetx_web",
                    "share_code": "ABC12345",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ingested"] == 1


def test_micro_feedback(client):
    resp = client.post(
        "/v1/feedback/micro",
        json={
            "context": "planetx_result",
            "score": 1,
            "session_id": "sess-2",
            "platform": "planetx_web",
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["ok"] is True


def test_funnel_stats_after_closed_loop(client):
    seeker_token = _register(client, "funnel-seeker@test.local")
    client.post(
        "/v1/game/profile-sync",
        headers={"Authorization": f"Bearer {seeker_token}"},
        json={
            "personality_type": "星云艺术家",
            "personality_detail": json.dumps({"name": "星云艺术家", "traits": ["创造力"]}),
        },
    )
    share = client.post(
        "/v1/referral/create",
        headers={"Authorization": f"Bearer {seeker_token}"},
        json={"purpose": "profile_share"},
    ).get_json()
    code = share["code"]

    client.get(f"/v1/referral/profile-view/{code}")

    hr_token = _register(client, "funnel-hr@test.local")
    client.post(
        "/v1/enterprise/create",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"name": "Funnel Corp"},
    )
    # 需要升级为付费 tier 才能导入候选人
    client.post(
        "/v1/payment/upgrade",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"tier": "pro"},
    )
    client.post(
        "/v1/enterprise/candidates/import-share",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"share_code": code},
    )

    # Funnel is admin-only (paid HR free-tier upgrade alone is not enough)
    freeish = client.get(
        "/v1/analytics/funnel",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert freeish.status_code == 403

    _promote_admin(client, "funnel-hr@test.local")
    # Re-login so JWT/DB role is consistent for require_auth DB lookup
    admin_token = client.post(
        "/v1/auth/login",
        json={"email": "funnel-hr@test.local", "password": "test-pass-123"},
    ).get_json()["access_token"]

    stats = client.get(
        "/v1/analytics/funnel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert stats.status_code == 200
    body = stats.get_json()
    assert body["steps"]["quiz_complete"] >= 1
    assert body["steps"]["share_code_created"] >= 1
    assert body["steps"]["profile_view_public"] >= 1
    assert body["steps"]["candidate_imported"] >= 1
    assert body["steps"]["trial_started"] >= 1


def test_invalid_event_rejected(client):
    resp = client.post(
        "/v1/analytics/events",
        json={"events": [{"event_name": "not_a_real_event"}]},
    )
    assert resp.status_code == 400
