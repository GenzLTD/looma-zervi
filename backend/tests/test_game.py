"""
Game routes tests — profile, mission, fleet CRUD.
Run: pytest tests/test_game.py -v
"""
import pytest
import sys
import os
import tempfile

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def app():
    """Create a test app with a temporary database file."""
    # :memory: doesn't persist across connections in SQLite,
    # so use a temp file that auto-deletes after the test session.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
    from src.app import create_app
    _app = create_app("testing")
    yield _app

    # Cleanup temp DB file
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authed_client(client):
    """Register a user and return client with auth headers pre-set."""
    resp = client.post("/v1/auth/register", json={
        "email": "gamer@test.com",
        "password": "password123",
        "name": "Game Tester",
    })
    data = resp.get_json()
    token = data["access_token"]
    user_id = data["user"]["id"]

    class AuthedClient:
        def __init__(self, test_client, auth_token, uid):
            self._client = test_client
            self.token = auth_token
            self.user_id = uid
            self.headers = {"Authorization": f"Bearer {auth_token}"}

        def get(self, url, **kwargs):
            return self._client.get(url, headers=self.headers, **kwargs)

        def post(self, url, json=None, **kwargs):
            return self._client.post(url, headers=self.headers, json=json, **kwargs)

    return AuthedClient(client, token, user_id)


@pytest.fixture
def second_authed_client(client):
    """Register a second user (for fleet join tests)."""
    resp = client.post("/v1/auth/register", json={
        "email": "gamer2@test.com",
        "password": "password123",
        "name": "Game Tester 2",
    })
    data = resp.get_json()
    token = data["access_token"]
    user_id = data["user"]["id"]

    class AuthedClient:
        def __init__(self, test_client, auth_token, uid):
            self._client = test_client
            self.token = auth_token
            self.user_id = uid
            self.headers = {"Authorization": f"Bearer {auth_token}"}

        def get(self, url, **kwargs):
            return self._client.get(url, headers=self.headers, **kwargs)

        def post(self, url, json=None, **kwargs):
            return self._client.post(url, headers=self.headers, json=json, **kwargs)

    return AuthedClient(client, token, user_id)


# ── Game profile ──

def test_sync_personality(authed_client):
    """Sync personality result should create/update game profile."""
    resp = authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "INTJ",
        "personality_detail": '{"traits": ["strategic", "analytical"]}',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["personality_type"] == "INTJ"
    assert "xp" in data
    assert "level" in data


def test_sync_personality_missing_type(authed_client):
    """Missing personality_type and identity should return 400."""
    resp = authed_client.post("/v1/game/profile-sync", json={
        "personality_detail": "some detail",
    })
    assert resp.status_code == 400


def test_sync_identity_only(authed_client):
    """PlanetX onboarding identity can sync without personality."""
    resp = authed_client.post("/v1/game/profile-sync", json={
        "identity": "explorer",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["identity"] == "explorer"

    profile = authed_client.get("/v1/game/profile").get_json()
    assert profile["identity"] == "explorer"


def test_sync_identity_invalid(authed_client):
    resp = authed_client.post("/v1/game/profile-sync", json={
        "identity": "invalid_role",
    })
    assert resp.status_code == 400


def test_get_game_profile_not_found(authed_client):
    """User with no profile should get 200 with default profile."""
    resp = authed_client.get("/v1/game/profile")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["xp"] == 0
    assert data["level"] == 1
    assert data["personality_type"] == ""


def test_get_game_profile_after_sync(authed_client):
    """After syncing personality, profile should be retrievable."""
    authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "ENFP",
        "personality_detail": '{"traits": ["creative"]}',
    })
    resp = authed_client.get("/v1/game/profile")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["personality_type"] == "ENFP"
    assert data["xp"] == 0
    assert data["level"] == 1
    assert data["missions_completed"] == []


def test_profile_requires_auth(client):
    """Game profile endpoint should require auth."""
    resp = client.get("/v1/game/profile")
    assert resp.status_code == 401


# ── Mission ──

def test_complete_mission(authed_client):
    """Complete a mission should award XP."""
    # First create a profile
    authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "INTJ",
    })

    resp = authed_client.post("/v1/game/mission-complete", json={
        "mission_id": "mission_stellar_quiz",
        "xp_reward": 50,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mission_id"] == "mission_stellar_quiz"
    assert data["xp_earned"] == 50
    assert data["total_xp"] >= 50
    assert data["level"] >= 1


def test_complete_mission_no_profile(authed_client):
    """Complete mission without profile should auto-create stub."""
    resp = authed_client.post("/v1/game/mission-complete", json={
        "mission_id": "mission_first_login",
        "xp_reward": 10,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["xp_earned"] == 10


def test_complete_mission_missing_id(authed_client):
    """Missing mission_id should return 400."""
    resp = authed_client.post("/v1/game/mission-complete", json={
        "xp_reward": 10,
    })
    assert resp.status_code == 400


def test_complete_mission_negative_xp(authed_client):
    """Negative xp_reward should return 400."""
    resp = authed_client.post("/v1/game/mission-complete", json={
        "mission_id": "mission_test",
        "xp_reward": -5,
    })
    assert resp.status_code == 400


def test_complete_mission_double(authed_client):
    """Same mission completed twice should return 409."""
    authed_client.post("/v1/game/profile-sync", json={"personality_type": "INTJ"})

    resp1 = authed_client.post("/v1/game/mission-complete", json={
        "mission_id": "mission_unique",
        "xp_reward": 20,
    })
    assert resp1.status_code == 200

    resp2 = authed_client.post("/v1/game/mission-complete", json={
        "mission_id": "mission_unique",
        "xp_reward": 20,
    })
    assert resp2.status_code == 409
    assert resp2.get_json()["error"] == "already_completed"


def test_mission_xp_updates_level(authed_client):
    """After enough XP, level should increase."""
    authed_client.post("/v1/game/profile-sync", json={"personality_type": "INTJ"})

    # Complete several missions to accumulate XP
    for i in range(5):
        authed_client.post("/v1/game/mission-complete", json={
            "mission_id": f"mission_batch_{i}",
            "xp_reward": 100,
        })

    resp = authed_client.get("/v1/game/profile")
    data = resp.get_json()
    assert data["xp"] >= 500
    assert data["level"] >= 3  # sqrt(500/100)+1 = ~3.2 → 3


# ── Fleet ──

def test_create_fleet(authed_client):
    """Create a fleet should return fleet details with captain as member."""
    resp = authed_client.post("/v1/game/fleet/create", json={
        "name": "Alpha Fleet",
        "description": "The first fleet",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Alpha Fleet"
    assert data["captain_id"] == authed_client.user_id
    assert data["member_count"] == 1  # captain auto-joins


def test_create_fleet_missing_name(authed_client):
    """Missing fleet name should return 400."""
    resp = authed_client.post("/v1/game/fleet/create", json={
        "description": "No name",
    })
    assert resp.status_code == 400


def test_create_fleet_name_too_long(authed_client):
    """Fleet name > 50 chars should return 400."""
    resp = authed_client.post("/v1/game/fleet/create", json={
        "name": "A" * 51,
    })
    assert resp.status_code == 400


def test_create_fleet_while_in_one(authed_client):
    """User already in fleet cannot create another (MVP: one fleet per user)."""
    authed_client.post("/v1/game/fleet/create", json={
        "name": "First Fleet",
    })
    resp = authed_client.post("/v1/game/fleet/create", json={
        "name": "Second Fleet",
    })
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "already_in_fleet"


def test_join_fleet(authed_client, second_authed_client):
    """Second user can join first user's fleet."""
    resp = authed_client.post("/v1/game/fleet/create", json={
        "name": "Alpha Fleet",
    })
    fleet_id = resp.get_json()["id"]

    resp = second_authed_client.post("/v1/game/fleet/join", json={
        "fleet_id": fleet_id,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fleet_id"] == fleet_id
    assert data["member_count"] == 2


def test_join_fleet_missing_id(second_authed_client):
    """Missing fleet_id should return 400."""
    resp = second_authed_client.post("/v1/game/fleet/join", json={})
    assert resp.status_code == 400


def test_join_nonexistent_fleet(second_authed_client):
    """Joining a fleet that doesn't exist should return 404."""
    resp = second_authed_client.post("/v1/game/fleet/join", json={
        "fleet_id": "nonexistent-id",
    })
    assert resp.status_code == 404


def test_join_fleet_already_in_one(authed_client, second_authed_client):
    """User already in fleet cannot join another."""
    # Second user creates their own fleet
    second_authed_client.post("/v1/game/fleet/create", json={
        "name": "Second Fleet",
    })
    # First user creates fleet
    resp = authed_client.post("/v1/game/fleet/create", json={
        "name": "Alpha Fleet",
    })
    fleet_id = resp.get_json()["id"]

    # Second user tries to join first user's fleet — but already in their own
    resp = second_authed_client.post("/v1/game/fleet/join", json={
        "fleet_id": fleet_id,
    })
    assert resp.status_code == 409


def test_my_fleet(authed_client):
    """Get my fleet should return fleet details and members."""
    authed_client.post("/v1/game/fleet/create", json={
        "name": "Alpha Fleet",
        "description": "Test fleet",
    })

    resp = authed_client.get("/v1/game/fleet/mine")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fleet"] is not None
    assert data["fleet"]["name"] == "Alpha Fleet"
    assert data["member_count"] == 1
    assert len(data["members"]) == 1


def test_my_fleet_none(authed_client):
    """User not in any fleet should get fleet=None."""
    resp = authed_client.get("/v1/game/fleet/mine")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fleet"] is None


def test_leave_fleet(authed_client, second_authed_client):
    """Non-captain member can leave fleet."""
    resp = authed_client.post("/v1/game/fleet/create", json={
        "name": "Alpha Fleet",
    })
    fleet_id = resp.get_json()["id"]

    second_authed_client.post("/v1/game/fleet/join", json={
        "fleet_id": fleet_id,
    })

    # Second user leaves
    resp = second_authed_client.post("/v1/game/fleet/leave")
    assert resp.status_code == 200

    # Verify second user is no longer in fleet
    resp = second_authed_client.get("/v1/game/fleet/mine")
    assert resp.get_json()["fleet"] is None


def test_captain_cannot_leave(authed_client):
    """Captain cannot leave fleet — must dissolve."""
    authed_client.post("/v1/game/fleet/create", json={
        "name": "Alpha Fleet",
    })

    resp = authed_client.post("/v1/game/fleet/leave")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "captain_cannot_leave"


def test_leave_fleet_not_in_one(authed_client):
    """User not in any fleet — leave should succeed silently."""
    resp = authed_client.post("/v1/game/fleet/leave")
    assert resp.status_code == 200


def test_fleet_requires_auth(client):
    """Fleet endpoints should require auth."""
    resp = client.get("/v1/game/fleet/mine")
    assert resp.status_code == 401
    resp = client.post("/v1/game/fleet/create", json={"name": "test"})
    assert resp.status_code == 401


# ── Integration: profile + mission + fleet ──

def test_full_game_flow(authed_client, second_authed_client):
    """Full flow: sync personality → complete missions → create fleet → join."""
    # 1. Sync personality
    resp = authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "INTJ",
        "personality_detail": '{"traits": ["strategic"]}',
    })
    assert resp.status_code == 200

    # 2. Complete missions
    for i in range(3):
        authed_client.post("/v1/game/mission-complete", json={
            "mission_id": f"mission_flow_{i}",
            "xp_reward": 50,
        })

    # 3. Check profile has XP
    resp = authed_client.get("/v1/game/profile")
    data = resp.get_json()
    assert data["xp"] >= 150
    assert len(data["missions_completed"]) == 3

    # 4. Create fleet
    resp = authed_client.post("/v1/game/fleet/create", json={
        "name": "Stellar Squad",
        "description": "Join the stars",
    })
    assert resp.status_code == 201
    fleet_id = resp.get_json()["id"]

    # 5. Second user syncs + joins
    second_authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "ENFP",
    })
    resp = second_authed_client.post("/v1/game/fleet/join", json={
        "fleet_id": fleet_id,
    })
    assert resp.status_code == 200

    # 6. Check fleet has 2 members
    resp = authed_client.get("/v1/game/fleet/mine")
    data = resp.get_json()
    assert data["member_count"] == 2
    assert len(data["members"]) == 2


# ── Fleet match ──

def test_match_requires_personality(authed_client):
    """Match without personality should 400."""
    resp = authed_client.post("/v1/game/match", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "personality_required"


def test_match_requires_fleet(authed_client):
    """Match without fleet should 400."""
    authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "星云艺术家",
    })
    resp = authed_client.post("/v1/game/match", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "fleet_required"


def test_match_fleet_too_small(authed_client):
    """Solo fleet cannot match."""
    authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "星云艺术家",
    })
    authed_client.post("/v1/game/fleet/create", json={"name": "Solo Fleet"})
    resp = authed_client.post("/v1/game/match", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "fleet_too_small"


def test_match_complementary_personality(authed_client, second_authed_client):
    """Complementary types should score highest and allow mission complete."""
    # Captain: 星云艺术家
    authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "星云艺术家",
    })
    resp = authed_client.post("/v1/game/fleet/create", json={"name": "Match Fleet"})
    fleet_id = resp.get_json()["id"]

    # Mate: complementary 黑洞程序员
    second_authed_client.post("/v1/game/profile-sync", json={
        "personality_type": "黑洞程序员",
        "personality_detail": '{"emoji":"💻"}',
    })
    second_authed_client.post("/v1/game/fleet/join", json={"fleet_id": fleet_id})

    resp = authed_client.post("/v1/game/match", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["matched"] is True
    assert data["match"]["user_id"] == second_authed_client.user_id
    assert data["match"]["personality_type"] == "黑洞程序员"
    assert data["match"]["match_score"] == 95
    assert data["match_mode"] == "complementary"
    assert "互补" in data["match"]["reason"]
    assert data["self"]["personality_type"] == "星云艺术家"


def test_match_prefers_complementary_over_same(authed_client, second_authed_client, client):
    """When multiple candidates exist, complementary beats same-type."""
    authed_client.post("/v1/game/profile-sync", json={"personality_type": "星云艺术家"})
    resp = authed_client.post("/v1/game/fleet/create", json={"name": "Trio Fleet"})
    fleet_id = resp.get_json()["id"]

    # Same-type member
    second_authed_client.post("/v1/game/profile-sync", json={"personality_type": "星云艺术家"})
    second_authed_client.post("/v1/game/fleet/join", json={"fleet_id": fleet_id})

    # Complementary member
    resp3 = client.post("/v1/auth/register", json={
        "email": "gamer3@test.com",
        "password": "password123",
        "name": "Game Tester 3",
    })
    token3 = resp3.get_json()["access_token"]
    uid3 = resp3.get_json()["user"]["id"]
    headers3 = {"Authorization": f"Bearer {token3}"}
    client.post("/v1/game/profile-sync", headers=headers3, json={
        "personality_type": "黑洞程序员",
    })
    client.post("/v1/game/fleet/join", headers=headers3, json={"fleet_id": fleet_id})

    resp = authed_client.post("/v1/game/match", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["match"]["user_id"] == uid3
    assert data["match"]["match_score"] == 95
    assert data["match_mode"] == "complementary"
    assert data["candidates_considered"] == 2


def test_match_random_fallback_when_no_complementary(authed_client, second_authed_client):
    """Without complementary mates, pick randomly and still clear mission threshold."""
    authed_client.post("/v1/game/profile-sync", json={"personality_type": "星云艺术家"})
    resp = authed_client.post("/v1/game/fleet/create", json={"name": "Random Fleet"})
    fleet_id = resp.get_json()["id"]

    # Same-type only — no complementary
    second_authed_client.post("/v1/game/profile-sync", json={"personality_type": "星云艺术家"})
    second_authed_client.post("/v1/game/fleet/join", json={"fleet_id": fleet_id})

    resp = authed_client.post("/v1/game/match", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["matched"] is True
    assert data["match"]["user_id"] == second_authed_client.user_id
    assert data["match_mode"] == "same_type"
    assert data["match"]["match_score"] == 72
    assert "同频共振" in data["match"]["reason"]


def test_match_random_among_multiple_complementary(authed_client, second_authed_client, client):
    """Multiple complementary candidates → highest-score match returned."""
    authed_client.post("/v1/game/profile-sync", json={"personality_type": "星云艺术家"})
    resp = authed_client.post("/v1/game/fleet/create", json={"name": "Dual Comp Fleet"})
    fleet_id = resp.get_json()["id"]

    second_authed_client.post("/v1/game/profile-sync", json={"personality_type": "黑洞程序员"})
    second_authed_client.post("/v1/game/fleet/join", json={"fleet_id": fleet_id})

    resp3 = client.post("/v1/auth/register", json={
        "email": "gamer4@test.com",
        "password": "password123",
        "name": "Game Tester 4",
    })
    token4 = resp3.get_json()["access_token"]
    uid4 = resp3.get_json()["user"]["id"]
    headers4 = {"Authorization": f"Bearer {token4}"}
    client.post("/v1/game/profile-sync", headers=headers4, json={"personality_type": "黑洞程序员"})
    client.post("/v1/game/fleet/join", headers=headers4, json={"fleet_id": fleet_id})

    resp = authed_client.post("/v1/game/match", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["match_mode"] == "complementary"
    assert data["match"]["match_score"] == 95
    assert data["match"]["user_id"] in {second_authed_client.user_id, uid4}
    assert data["candidates_considered"] == 2


def test_match_creates_consensus_and_acknowledge(authed_client, second_authed_client):
    """P0-3: match writes match_consensus; candidate can acknowledge."""
    authed_client.post("/v1/game/profile-sync", json={"personality_type": "星云艺术家"})
    fleet_id = authed_client.post(
        "/v1/game/fleet/create", json={"name": "Consensus Fleet"}
    ).get_json()["id"]

    second_authed_client.post(
        "/v1/game/profile-sync", json={"personality_type": "黑洞程序员"}
    )
    second_authed_client.post("/v1/game/fleet/join", json={"fleet_id": fleet_id})

    match = authed_client.post("/v1/game/match", json={}).get_json()
    assert match["matched"] is True
    assert match["can_complete_mission"] is True
    assert match.get("pending_consensus_id")
    assert match.get("consensus_status") in (
        "consensus_passed",
        "consensus_verified",
        "consensus_weak",
    )

    cid = match["pending_consensus_id"]
    ack = second_authed_client.post(
        "/v1/game/match/acknowledge",
        json={"consensus_id": cid, "action": "accept"},
    )
    assert ack.status_code == 200
    body = ack.get_json()
    assert body["status"] == "verified"
    assert body["consensus_status"] == "consensus_verified"

    listing = second_authed_client.get("/v1/game/match/consensus")
    assert listing.status_code == 200
    verified = listing.get_json()["verified"]
    assert any(v["id"] == cid for v in verified)


def test_profile_includes_spread_count(authed_client, second_authed_client, client):
    """P0-2: spread_count counts invitees who completed personality."""
    # Create referral invite (not profile_share)
    create = authed_client.post("/v1/referral/create", json={"purpose": "referral"})
    assert create.status_code in (200, 201)
    code = create.get_json()["code"]

    # Invitee registers separately then uses code + completes personality
    second_authed_client.post("/v1/referral/use", json={"code": code})
    second_authed_client.post(
        "/v1/game/profile-sync", json={"personality_type": "超新星领航员"}
    )
    second_authed_client.post(
        "/v1/game/mission-complete",
        json={"mission_id": "personality", "xp_reward": 50},
    )

    profile = authed_client.get("/v1/game/profile").get_json()
    assert "spread_count" in profile
    assert profile["spread_count"] >= 1


def test_social_degrees_has_no_trust_score(authed_client, second_authed_client):
    """P0-0: social API must not expose trust_score(degrees)."""
    # Build a referral edge so degrees can resolve
    create = authed_client.post("/v1/referral/create", json={"purpose": "referral"})
    code = create.get_json()["code"]
    second_authed_client.post("/v1/referral/use", json={"code": code})

    resp = authed_client.get(f"/v1/social/degrees/{second_authed_client.user_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "degrees" in data
    assert "trust_score" not in data

    conn = authed_client.get(f"/v1/social/connection/{second_authed_client.user_id}")
    assert conn.status_code == 200
    assert "trust_score" not in conn.get_json()
