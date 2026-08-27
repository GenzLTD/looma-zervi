"""
Trust layer tests — trust_agent attestation generation & retrieval.
Run: pytest tests/test_trust.py -v
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
    from src.app import create_app
    _app = create_app("testing")
    yield _app
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, email, name):
    resp = client.post("/v1/auth/register", json={
        "email": email,
        "password": "password123",
        "name": name,
    })
    data = resp.get_json()
    return data["access_token"], data["user"]["id"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestAttestationFlow:
    """Trust Agent attestation generation via refresh + retrieval."""

    def test_generate_and_retrieve_attestations(self, client):
        """Insert trust memories → POST /v1/trust/refresh → GET /v1/trust/attestations."""
        token, uid = _register(client, "trust_gen@test.com", "TrustGen")

        # Sync game profile — required for trust_agent to read display_name
        client.post(
            "/v1/game/profile-sync",
            headers=_headers(token),
            json={"personality_type": "星云艺术家"},
        )

        # Insert trust memories directly via DB (dicts, not JSON strings —
        # insert_trust_memory calls json.dumps internally)
        db = client.application._db
        db.insert_trust_memory(
            user_id=uid,
            session_type="quiz",
            session_id="ses-001",
            memory_content={"score": 95},
        )
        db.insert_trust_memory(
            user_id=uid,
            session_type="fleet",
            session_id="ses-002",
            memory_content={"action": "join_fleet"},
        )
        db.insert_trust_memory(
            user_id=uid,
            session_type="ask",
            session_id="ses-003",
            memory_content={"question": "什么是信任？"},
        )

        # Trigger attestation generation
        refresh = client.post("/v1/trust/refresh", headers=_headers(token))
        assert refresh.status_code == 200
        refresh_data = refresh.get_json()
        assert refresh_data["message"] == "attestations refreshed"
        assert refresh_data["total"] >= 1

        # Retrieve attestations
        resp = client.get("/v1/trust/attestations", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        atts = data["attestations"]
        claim_types = [a["claim_type"] for a in atts]
        # With quiz + fleet + ask memories, should have identity + collaboration + communication
        assert "identity" in claim_types
        assert "collaboration" in claim_types
        assert "communication" in claim_types

    def test_attestations_empty_without_refresh(self, client):
        """Without refresh, attestations should be empty until memories are seeded."""
        token, _ = _register(client, "trust_empty@test.com", "Empty")

        # No memories inserted, no refresh called
        resp = client.get("/v1/trust/attestations", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert data["attestations"] == []

    def test_attestations_requires_auth(self, client):
        """Unauthenticated GET should return 401."""
        resp = client.get("/v1/trust/attestations")
        assert resp.status_code == 401

    def test_resume_match_bridge_mints_weak_identity(self, client):
        """T-space resume/match memories alone should mint weak identity (not empty)."""
        token, uid = _register(client, "trust_bridge@test.com", "Bridge")
        db = client.application._db
        db.insert_trust_memory(
            user_id=uid,
            session_type="resume",
            session_id="resume-1",
            memory_content={"skills_claimed": ["Python"]},
        )
        db.insert_trust_memory(
            user_id=uid,
            session_type="match",
            session_id="match-1",
            memory_content={"top_score": 80},
        )
        refresh = client.post("/v1/trust/refresh", headers=_headers(token))
        assert refresh.status_code == 200
        assert refresh.get_json()["total"] >= 1
        resp = client.get("/v1/trust/attestations", headers=_headers(token))
        data = resp.get_json()
        identity = next(a for a in data["attestations"] if a["claim_type"] == "identity")
        assert identity["verification_status"] == "weak"
        assert identity["evidence_type"] == "resume"

    def test_refresh_requires_auth(self, client):
        """Unauthenticated POST refresh should return 401."""
        resp = client.post("/v1/trust/refresh")
        assert resp.status_code == 401

    def test_refresh_then_re_fetch_consistent(self, client):
        """Refresh twice and verify attestation IDs are stable (upsert behaviour)."""
        token, uid = _register(client, "trust_stable@test.com", "Stable")

        client.post(
            "/v1/game/profile-sync",
            headers=_headers(token),
            json={"personality_type": "黑洞程序员"},
        )

        db = client.application._db
        db.insert_trust_memory(
            user_id=uid,
            session_type="fleet",
            session_id="ses-f1",
            memory_content={"action": "create_fleet"},
        )

        # First refresh
        r1 = client.post("/v1/trust/refresh", headers=_headers(token))
        assert r1.status_code == 200
        a1 = client.get("/v1/trust/attestations", headers=_headers(token))
        atts1 = a1.get_json()["attestations"]

        # Second refresh — same memories, should upsert not duplicate
        r2 = client.post("/v1/trust/refresh", headers=_headers(token))
        assert r2.status_code == 200
        a2 = client.get("/v1/trust/attestations", headers=_headers(token))
        atts2 = a2.get_json()["attestations"]

        assert len(atts2) == len(atts1)
        # trust.v1 public schema uses attestation_id (not raw DB id)
        ids1 = sorted(a["attestation_id"] for a in atts1)
        ids2 = sorted(a["attestation_id"] for a in atts2)
        assert ids1 == ids2
        assert all(a.get("signature") for a in atts2)
