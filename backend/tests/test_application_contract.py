"""P2: application binds resume_id to job_id; withdraw hides resume body from HR."""
from __future__ import annotations

import json


def _register(client, email: str, name: str = "User", role: str | None = None):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password123", "name": name},
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, headers, data


def _grant_jobseeker(client, headers: dict) -> None:
    grant = client.post(
        "/v1/compliance/consent/grant",
        headers=headers,
        json={"scope": "jobseeker_core"},
    )
    assert grant.status_code == 200, grant.get_json()


def _ingest_resume(client, headers: dict, markdown: str = "Python 工程师 5年") -> str:
    resp = client.post(
        "/v1/resume/ingest",
        headers=headers,
        json={"markdown": markdown, "filename": "cv.md", "extracted": {"skills": ["Python"]}},
    )
    assert resp.status_code == 200, resp.get_json()
    return str(resp.get_json()["resume_id"])


def test_application_submit_list_hr_and_withdraw(client, app):
    hr_id, hr_headers, _ = _register(client, "hr-app@test.com", name="HR")
    seeker_id, seeker_headers, _ = _register(client, "seeker-app@test.com", name="Seeker")
    _grant_jobseeker(client, seeker_headers)

    # HR seeds a job they own
    seed = client.post("/v1/jobs/seed-demo", headers=hr_headers, json={
        "jobs": [{
            "id": "PLANETX-JF-001",
            "title": "后端工程师",
            "company": "PlanetX",
            "description": "Python / Flask",
        }],
    })
    assert seed.status_code == 200, seed.get_json()
    assert "PLANETX-JF-001" in seed.get_json()["created"]

    # Jobs list should include seeded job
    jobs = client.get("/v1/jobs/list", headers=seeker_headers)
    assert jobs.status_code == 200
    ids = [j["id"] for j in jobs.get_json()["jobs"]]
    assert "PLANETX-JF-001" in ids

    resume_id = _ingest_resume(client, seeker_headers)

    # Create application
    create = client.post(
        "/v1/application",
        headers=seeker_headers,
        json={"resume_id": resume_id, "job_id": "PLANETX-JF-001", "enterprise_id": "ent-1"},
    )
    assert create.status_code == 201, create.get_json()
    body = create.get_json()
    assert body["already_exists"] is False
    app_id = body["application"]["id"]
    assert body["application"]["status"] == "submitted"
    assert body["application"]["resume_id"] == resume_id

    # Idempotent re-submit
    again = client.post(
        "/v1/application",
        headers=seeker_headers,
        json={"resume_id": resume_id, "job_id": "PLANETX-JF-001"},
    )
    assert again.status_code == 200
    assert again.get_json()["already_exists"] is True

    # Seeker list
    mine = client.get("/v1/application", headers=seeker_headers)
    assert mine.status_code == 200
    assert mine.get_json()["total"] == 1

    # HR sees active application with resume body
    hr_list = client.get(
        "/v1/jobs/PLANETX-JF-001/applications",
        headers=hr_headers,
    )
    assert hr_list.status_code == 200, hr_list.get_json()
    items = hr_list.get_json()["applications"]
    assert len(items) == 1
    assert items[0]["resume"]["markdown"]
    assert "Python" in (items[0]["resume"]["markdown"] or "")

    # Withdraw
    wd = client.delete(f"/v1/application/{app_id}", headers=seeker_headers)
    assert wd.status_code == 200
    assert wd.get_json()["application"]["status"] == "withdrawn"

    # HR active list empty
    hr_list2 = client.get(
        "/v1/jobs/PLANETX-JF-001/applications",
        headers=hr_headers,
    )
    assert hr_list2.get_json()["total"] == 0

    # HR detail with include_withdrawn: body redacted
    hr_all = client.get(
        "/v1/jobs/PLANETX-JF-001/applications?include_withdrawn=true",
        headers=hr_headers,
    )
    assert hr_all.get_json()["total"] == 1
    resume = hr_all.get_json()["applications"][0]["resume"]
    assert resume.get("redacted") is True
    assert resume.get("markdown") is None

    detail = client.get(f"/v1/application/{app_id}", headers=hr_headers)
    assert detail.status_code == 200
    assert detail.get_json()["resume"].get("redacted") is True


def test_application_requires_consent_and_ownership(client, app):
    seeker_id, seeker_headers, _ = _register(client, "seeker-noconsent@test.com")
    # no consent
    resp = client.post(
        "/v1/application",
        headers=seeker_headers,
        json={"resume_id": "1", "job_id": "j1"},
    )
    assert resp.status_code == 403

    _grant_jobseeker(client, seeker_headers)
    other_id, other_headers, _ = _register(client, "other-resume@test.com")
    _grant_jobseeker(client, other_headers)
    rid = _ingest_resume(client, other_headers, "Other person CV")

    # Cannot apply with someone else's resume
    bad = client.post(
        "/v1/application",
        headers=seeker_headers,
        json={"resume_id": rid, "job_id": "j1"},
    )
    assert bad.status_code == 404


def test_application_report_lazy_cache_and_auth(client, app, monkeypatch):
    """GET /v1/application/<id>/report — auth + lazy compute + cache hit."""
    hr_id, hr_headers, _ = _register(client, "hr-report@test.com", name="HR")
    seeker_id, seeker_headers, _ = _register(client, "seeker-report@test.com", name="Seeker")
    stranger_id, stranger_headers, _ = _register(client, "stranger-report@test.com")
    _grant_jobseeker(client, seeker_headers)

    seed = client.post(
        "/v1/jobs/seed-demo",
        headers=hr_headers,
        json={
            "jobs": [{
                "id": "JOB-REPORT-1",
                "title": "Python 后端工程师",
                "company": "Looma",
                "description": "需要 Python FastAPI Docker Redis 经验",
            }],
        },
    )
    assert seed.status_code == 200, seed.get_json()

    resume_id = _ingest_resume(
        client,
        seeker_headers,
        "资深 Python 工程师，熟悉 FastAPI 与 PostgreSQL，做过微服务。",
    )
    create = client.post(
        "/v1/application",
        headers=seeker_headers,
        json={"resume_id": resume_id, "job_id": "JOB-REPORT-1"},
    )
    assert create.status_code == 201, create.get_json()
    app_id = create.get_json()["application"]["id"]

    # Force heuristic path (no LLM in unit tests)
    def _boom(*_a, **_k):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(
        "src.pipeline.job_match_pipeline.run_job_match_pipeline",
        _boom,
    )

    # Stranger forbidden
    forbidden = client.get(f"/v1/application/{app_id}/report", headers=stranger_headers)
    assert forbidden.status_code == 403

    # Seeker gets report
    r1 = client.get(f"/v1/application/{app_id}/report", headers=seeker_headers)
    assert r1.status_code == 200, r1.get_json()
    body = r1.get_json()
    assert body["application_id"] == app_id
    assert body["job_id"] == "JOB-REPORT-1"
    mr = body["match_report"]
    assert mr["cached"] is False
    assert "overall_score" in mr
    assert isinstance(mr["skill_match"]["matched"], list)
    report_id = mr["report_id"]

    # Second call hits cache
    r2 = client.get(f"/v1/application/{app_id}/report", headers=seeker_headers)
    assert r2.status_code == 200
    assert r2.get_json()["match_report"]["cached"] is True
    assert r2.get_json()["match_report"]["report_id"] == report_id

    # HR can read
    hr_r = client.get(f"/v1/application/{app_id}/report", headers=hr_headers)
    assert hr_r.status_code == 200
    assert hr_r.get_json()["match_report"]["cached"] is True
