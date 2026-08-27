"""Match report persistence — minimal closed loop."""
import pytest

from src.db.manager import DatabaseManager
from src.reports.match_report_manager import MatchReportManager


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    mgr = DatabaseManager(path)
    mgr.init_schema()
    uid = mgr.create_user(email="match@test.com", password_hash="x", name="Tester")
    return mgr, uid


def _sample_matches():
    return [
        {
            "title": "后端工程师",
            "company": "测试科技",
            "location": "深圳",
            "salary_range": "30-50K",
            "reason": "技能匹配",
            "matched_skills": ["Python"],
            "missing_skills": ["K8s"],
            "fit_bullets": ["经历相关"],
            "gap_analysis": [
                {
                    "skill": "K8s",
                    "current_level": "了解",
                    "required_level": "熟练",
                    "gap": "缺实战",
                    "suggestion": "做实验",
                    "estimated_effort": "2周",
                    "priority": "high",
                }
            ],
            "improvement_plan": "学习 K8s",
            "scores": {
                "overall": 82,
                "background_match": 8,
                "skills_overlap": 24,
                "experience_relevance": 22,
                "seniority": 7,
                "language_requirement": 8,
                "company_score": 7,
                "salary_match": 6,
                "location_match": 8,
                "culture_workload_match": 5,
            },
        }
    ]


def test_create_list_get_delete(db):
    mgr, uid = db
    reports = MatchReportManager(mgr)

    created = reports.create_report(
        user_id=uid,
        resume_text="张三 手机 13800138000 Python 工程师",
        matches=_sample_matches(),
        title="测试报告",
    )
    assert created["id"]
    assert created["title"] == "测试报告"
    assert len(created["items"]) == 1
    assert created["items"][0]["overall_score"] == 82
    assert created["items"][0]["gap_analysis"][0]["skill"] == "K8s"
    # PII redacted in snapshot
    assert "13800138000" not in (created.get("resume_snapshot") or "")

    listed = reports.list_user_reports(uid)
    assert listed["total"] == 1
    assert listed["reports"][0]["id"] == created["id"]

    detail = reports.get_report(created["id"], user_id=uid)
    assert detail is not None
    assert detail["items"][0]["company_name"] == "测试科技"

    sharing = reports.share_report(
        report_id=created["id"],
        user_id=uid,
        shared_dimensions=["skills", "scores", "gap_analysis"],
        purpose="test",
    )
    assert sharing["status"] == "active"
    assert "skills" in sharing["shared_dimensions"]

    revoked = reports.revoke_sharing(sharing["id"], uid, created["id"])
    assert revoked["status"] == "revoked"

    assert reports.delete_report(created["id"], uid) is True
    assert reports.get_report(created["id"], user_id=uid) is None
    assert reports.list_user_reports(uid)["total"] == 0

    # Soft-deleted report can be purged immediately with days=0 not allowed;
    # use days=1 after forcing updated_at into the past.
    with mgr.get_conn() as conn:
        conn.execute(
            """UPDATE match_reports SET updated_at=datetime('now', '-40 days')
               WHERE id=?""",
            (created["id"],),
        )
    purged = reports.purge_deleted(days=30)
    assert purged["purged"] >= 1
