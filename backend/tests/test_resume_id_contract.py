"""A1: resume_id must be documents.id; list/analysis/delete are owner-scoped."""
from __future__ import annotations

import json


def _register(client, email: str = "resume-a1@test.com"):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password123", "name": "Resume A1"},
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, headers


def _grant_jobseeker_core(client, headers: dict) -> None:
    grant = client.post(
        "/v1/compliance/consent/grant",
        headers=headers,
        json={"scope": "jobseeker_core"},
    )
    assert grant.status_code == 200, grant.get_json()


def test_resume_id_roundtrip_list_analysis_delete(client, app):
    user_id, headers = _register(client)
    db = app._db

    with db.get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO documents (title, file_path, doc_type, file_size, metadata, status, created_at)
               VALUES (?, ?, 'resume', 1, ?, 'processed', datetime('now'))""",
            (
                "cv.pdf",
                f"resume/{user_id}/tmp.pdf",
                json.dumps(
                    {
                        "user_id": user_id,
                        "markdown": "Python Django 工程师",
                        "extracted": {"skills": ["Python"]},
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        rid = str(cur.lastrowid)
        conn.execute(
            "UPDATE documents SET file_path=? WHERE id=?",
            (f"resume/{user_id}/{rid}_cv.pdf", int(rid)),
        )

    listed = client.get("/v1/resume/list", headers=headers)
    assert listed.status_code == 200
    ids = {r["id"] for r in (listed.get_json() or {}).get("resumes") or []}
    assert rid in ids

    analysis = client.get(f"/v1/resume/analysis?resume_id={rid}", headers=headers)
    assert analysis.status_code != 404
    assert (analysis.get_json() or {}).get("resume_id") == rid

    deleted = client.delete(f"/v1/resume/{rid}", headers=headers)
    assert deleted.status_code == 200
    assert (deleted.get_json() or {}).get("resume_id") == rid

    gone = client.get(f"/v1/resume/analysis?resume_id={rid}", headers=headers)
    assert gone.status_code == 404


def test_resume_list_filters_by_owner(client, app):
    user_id, headers = _register(client, email="resume-a1-owner@test.com")
    db = app._db
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO documents (title, file_path, doc_type, file_size, metadata, status, created_at)
               VALUES ('other.pdf', 'resume/other/9_other.pdf', 'resume', 1, ?, 'processed', datetime('now'))""",
            (json.dumps({"user_id": "someone-else", "markdown": "x"}, ensure_ascii=False),),
        )
        conn.execute(
            """INSERT INTO documents (title, file_path, doc_type, file_size, metadata, status, created_at)
               VALUES ('mine.pdf', ?, 'resume', 1, ?, 'processed', datetime('now'))""",
            (
                f"resume/{user_id}/1_mine.pdf",
                json.dumps({"user_id": user_id, "markdown": "mine"}, ensure_ascii=False),
            ),
        )

    listed = client.get("/v1/resume/list", headers=headers)
    assert listed.status_code == 200
    resumes = (listed.get_json() or {}).get("resumes") or []
    assert len(resumes) >= 1
    for r in resumes:
        assert "resume/other/" not in str(r.get("filename") or "")


def test_format_match_report_block_empty_and_present():
    from src.agents.central_brain import _format_match_report_block

    assert _format_match_report_block({}) == ""
    assert _format_match_report_block({"match_report": None}) == ""
    block = _format_match_report_block(
        {
            "match_report": {
                "report_id": "r1",
                "title": "测试报告",
                "resume_summary": "Python",
                "top_items": [
                    {
                        "job_title": "后端",
                        "overall_score": 90,
                        "matched_skills": ["Python"],
                        "missing_skills": ["Go"],
                        "gap_analysis": "缺 Go",
                    }
                ],
            }
        }
    )
    assert "当前匹配报告上下文" in block
    assert "后端" in block
    assert "缺 Go" in block


# ── L-P0-1: Upload ALWAYS persists (even on LLM failure) ──


def test_upload_persists_even_on_llm_failure(client, app):
    """Upload a text file (not a valid resume) — should still get resume_id
    even if LLM extraction returns empty."""
    from io import BytesIO

    user_id, headers = _register(client, email="upload-llm-fail@test.com")
    _grant_jobseeker_core(client, headers)

    data = {"file": (BytesIO(b"Just some text, not a resume"), "not-a-resume.txt")}
    resp = client.post(
        "/v1/resume/upload",
        data=data,
        content_type="multipart/form-data",
        headers=headers,
    )
    body = resp.get_json() or {}

    # Key assertion: resume_id exists regardless of extraction outcome
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {body}"
    assert "resume_id" in body, f"No resume_id in response: {body}"
    assert body["resume_id"] is not None, "resume_id should be set (persisted before LLM)"
    assert "status" in body, f"No status in response: {body}"
    assert body["status"] in ("complete", "partial"), f"Unexpected status: {body['status']}"

    # Should have markdown (MarkItDown output)
    assert body.get("markdown"), "markdown should exist"

    # Verify it's actually in DB
    rid = body["resume_id"]
    analysis = client.get(f"/v1/resume/analysis?resume_id={rid}", headers=headers)
    assert analysis.status_code != 404, f"resume_id {rid} should be queryable in analysis"
    analysis_body = analysis.get_json() or {}
    assert analysis_body.get("resume_id") == rid

    # Delete should work too
    deleted = client.delete(f"/v1/resume/{rid}", headers=headers)
    assert deleted.status_code == 200


# ── L-P0-2: Ingest endpoint (DemoPeter thin-ingest) ──


def test_ingest_basic_roundtrip(client, app):
    """POST /v1/resume/ingest persists markdown, returns resume_id."""
    user_id, headers = _register(client, email="ingest-roundtrip@test.com")
    _grant_jobseeker_core(client, headers)

    resp = client.post(
        "/v1/resume/ingest",
        json={
            "markdown": "# DemoPeter Resume\n\nPython 5年经验\n熟悉 Django、FastAPI\n",
            "filename": "demopeter_resume.txt",
            "extracted": {
                "skills": ["Python", "Django", "FastAPI"],
                "years": 5,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json() or {}
    assert body.get("resume_id"), f"No resume_id in response: {body}"
    assert body["status"] == "processed"
    rid = body["resume_id"]

    # Verify in LIST
    listed = client.get("/v1/resume/list", headers=headers)
    assert listed.status_code == 200
    resumes = (listed.get_json() or {}).get("resumes") or []
    ids = {r["id"] for r in resumes}
    assert rid in ids, f"resume_id {rid} not in list: {ids}"

    # Verify ANALYSIS works
    analysis = client.get(f"/v1/resume/analysis?resume_id={rid}", headers=headers)
    assert analysis.status_code == 200
    analysis_body = analysis.get_json() or {}
    assert analysis_body.get("resume_id") == rid
    assert analysis_body.get("extracted") is not None

    # Cleanup
    deleted = client.delete(f"/v1/resume/{rid}", headers=headers)
    assert deleted.status_code == 200


def test_ingest_markdown_required(client, app):
    """POST /v1/resume/ingest requires non-empty markdown."""
    user_id, headers = _register(client, email="ingest-no-md@test.com")
    _grant_jobseeker_core(client, headers)

    resp = client.post(
        "/v1/resume/ingest",
        json={"markdown": ""},
        headers=headers,
    )
    assert resp.status_code == 400
    body = resp.get_json() or {}
    assert body.get("error") == "bad_request"


def test_ingest_without_extracted(client, app):
    """POST /v1/resume/ingest without extracted → status=stored."""
    user_id, headers = _register(client, email="ingest-no-extract@test.com")
    _grant_jobseeker_core(client, headers)

    resp = client.post(
        "/v1/resume/ingest",
        json={"markdown": "Plain text resume here.", "filename": "plain.txt"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json() or {}
    assert body["status"] == "stored"
    assert body.get("resume_id")

    # Cleanup
    client.delete(f"/v1/resume/{body['resume_id']}", headers=headers)


# ── L-P0-1 + L-P0-2 combined: partial upload → ingest → Ask compatibility ──


def test_partial_and_ingest_preserve_markdown_for_analysis(client, app):
    """Both partial-upload and ingest store markdown that powers
    analysis endpoint even without extracted data."""
    user_id, headers = _register(client, email="partial-markdown@test.com")
    _grant_jobseeker_core(client, headers)

    # Ingest a resume with markdown but no extracted
    resp = client.post(
        "/v1/resume/ingest",
        json={"markdown": "Python fullstack developer with 7 years experience", "filename": "cv.md"},
        headers=headers,
    )
    assert resp.status_code == 200
    rid = (resp.get_json() or {})["resume_id"]

    # ANALYSIS should still work (uses markdown_text fallback)
    analysis = client.get(f"/v1/resume/analysis?resume_id={rid}", headers=headers)
    assert analysis.status_code == 200
    analysis_body = analysis.get_json() or {}
    assert analysis_body.get("markdown") is not None
    assert "Python" in str(analysis_body)

    # Cleanup
    client.delete(f"/v1/resume/{rid}", headers=headers)
