"""职位分区间锁在 job_match.v1.json。这里锁住 looma 的夹取，避免只改 _clamp。"""
from src.pipeline.job_match_pipeline import _sanitize_scores

# 与 gfcc contracts/job_match.v1.json scores 一致。
BOUNDS = {
    "overall": (0, 100, 50),
    "background_match": (0, 10, 5),
    "skills_overlap": (0, 30, 15),
    "experience_relevance": (0, 30, 15),
    "seniority": (0, 10, 5),
    "language_requirement": (0, 10, 5),
    "company_score": (0, 10, 5),
    "salary_match": (0, 10, 5),
    "location_match": (0, 10, 5),
    "culture_workload_match": (0, 10, 5),
}


def test_scores_clamp_to_contract_max():
    raw = {name: 9999 for name in BOUNDS}
    got = _sanitize_scores(raw)
    for name, (_lo, hi, _default) in BOUNDS.items():
        assert got[name] == hi


def test_missing_scores_use_contract_default():
    got = _sanitize_scores({})
    for name, (_lo, _hi, default) in BOUNDS.items():
        assert got[name] == default


def test_job_scores_do_not_carry_value_axes():
    got = _sanitize_scores({"salary_match": 6, "overall": 80})
    assert set(BOUNDS).issuperset({"salary_match", "overall"})
    assert "value_axes" not in got
    assert "survival" not in got
    assert got["salary_match"] == 6
    assert got["overall"] == 80
