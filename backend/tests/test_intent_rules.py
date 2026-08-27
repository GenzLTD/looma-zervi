"""Intent keyword rules — avoid SaaS domain chips falling into poetry."""
from src.agents.central_brain import _parse_intent_rules


def test_health_domain_chip_is_not_poetry():
    assert _parse_intent_rules("情绪陪伴 · 压力疏导") != "poetry"
    assert _parse_intent_rules("情绪陪伴 · 压力疏导") == "rag"


def test_life_domain_chip_routes_to_rag():
    assert _parse_intent_rules("时间管理 · 效率提升") == "rag"


def test_explicit_poetry_still_matches():
    assert _parse_intent_rules("推荐一句诗") == "poetry"
    assert _parse_intent_rules("来首唐诗") == "poetry"
