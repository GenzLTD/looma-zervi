"""Unit tests for gap_analysis / missing_skills sanitization in job match pipeline."""
from src.pipeline.job_match_pipeline import _sanitize_scores, _default_score


def test_sanitize_scores_includes_gap_fields():
    raw = {
        "overall": 88,
        "background_match": 8,
        "skills_overlap": 26,
        "experience_relevance": 24,
        "seniority": 7,
        "language_requirement": 8,
        "company_score": 7,
        "salary_match": 6,
        "location_match": 8,
        "culture_workload_match": 5,
        "summary": "匹配良好",
        "keywords": ["Python", "Go"],
        "fit_bullets": ["技能重叠"],
        "missing_skills": ["分布式事务", ""],
        "gap_analysis": [
            {
                "skill": "分布式事务",
                "current_level": "了解",
                "required_level": "实战",
                "gap": "缺生产经验",
                "suggestion": "做 Demo",
                "estimated_effort": "2周",
                "priority": "HIGH",
            },
            {"skill": ""},  # dropped
        ],
        "improvement_plan": "## 计划\n1. 学习 Saga",
    }
    out = _sanitize_scores(raw)
    assert out["missing_skills"] == ["分布式事务"]
    assert len(out["gap_analysis"]) == 1
    assert out["gap_analysis"][0]["priority"] == "high"
    assert "Saga" in out["improvement_plan"]


def test_missing_skills_derived_from_gap():
    out = _sanitize_scores(
        {
            "overall": 70,
            "gap_analysis": [{"skill": "K8s", "priority": "medium"}],
        }
    )
    assert out["missing_skills"] == ["K8s"]


def test_improvement_plan_derived_when_llm_omits():
    out = _sanitize_scores(
        {
            "overall": 70,
            "summary": "技能接近，缺分布式经验",
            "gap_analysis": [
                {
                    "skill": "分布式事务",
                    "suggestion": "完成 Saga Demo",
                    "estimated_effort": "2周",
                    "priority": "high",
                }
            ],
            "improvement_plan": "",
        }
    )
    assert "提升路径" in out["improvement_plan"]
    assert "分布式事务" in out["improvement_plan"]
    assert "Saga" in out["improvement_plan"]


def test_default_score_has_gap_defaults():
    d = _default_score()
    assert d["missing_skills"] == []
    assert d["gap_analysis"] == []
    assert "提升路径" in d["improvement_plan"]
