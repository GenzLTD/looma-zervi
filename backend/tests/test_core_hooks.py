"""刀 5e/5f 门禁：核钩子（时间线埋点 / 匹配报告）与大脑桥的可注入性。

判据两条：
1. **注入生效** —— 宿主注册后，核调用的是注入实现（而不是还能 import 到产品模块就不报错）；
2. **缺省不出声** —— 未注册时回落惰性缺省：埋点失败被吞、报告拿不到返回 None、
   brain 拿不到抛 BrainNotConfigured（由 ask 的 try/except 兜成 500 + 退配额）。
"""
from __future__ import annotations

import pytest

from src.thomas_core import brain, hooks


@pytest.fixture(autouse=True)
def _clean_hooks():
    hooks.reset_hooks()
    brain.reset_brain()
    yield
    hooks.reset_hooks()
    brain.reset_brain()


def test_timeline_hook_receives_registered_callable():
    seen = {}

    def fake_logger(db, user_id, **kwargs):
        seen.update(db=db, user_id=user_id, kwargs=kwargs)

    hooks.register_timeline_logger(fake_logger)
    hooks.record_interaction_log("DB", "u-1", query="hi", intent="rag", ask_mode="chat")

    assert seen["db"] == "DB"
    assert seen["user_id"] == "u-1"
    assert seen["kwargs"]["intent"] == "rag"


def test_timeline_hook_swallows_failures():
    def boom(db, user_id, **kwargs):
        raise RuntimeError("timeline down")

    hooks.register_timeline_logger(boom)
    # 埋点是 best-effort：不能让一次时间线故障拖垮 /v1/ask
    assert hooks.record_interaction_log("DB", "u-1", query="hi") is None


def test_report_manager_factory_injection():
    class FakeMgr:
        def __init__(self, db):
            self.db = db

    hooks.register_report_manager_factory(FakeMgr)
    mgr = hooks.report_manager("DB")
    assert isinstance(mgr, FakeMgr) and mgr.db == "DB"


def test_report_manager_default_is_available_in_repo():
    """仓内默认实现应能懒加载到 MatchReportManager（改造前行为不变）。"""
    mgr = hooks.report_manager("DB")
    assert mgr is not None
    assert hasattr(mgr, "get_report")


def test_brain_injection_and_default():
    def fake_parse(query, navigator_mode=False):
        return "rag", 0.9, {}

    def fake_dispatch(**kwargs):
        return {"answer": "ok"}

    brain.register_brain(fake_parse, fake_dispatch)
    parse_intent, dispatch = brain.get_brain()
    assert parse_intent("q") == ("rag", 0.9, {})
    assert dispatch(intent="rag") == {"answer": "ok"}

    brain.reset_brain()
    parse_intent2, dispatch2 = brain.get_brain()
    assert callable(parse_intent2) and callable(dispatch2)
    intent, conf, slots = parse_intent2("介绍一下 THOMAS 架构的底座")
    assert isinstance(intent, str) and 0.0 <= float(conf) <= 1.0


def test_brain_missing_raises_clear_error(monkeypatch):
    """独立核仓里没有 src.agents：必须抛明确的 BrainNotConfigured，而不是静默空答案。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("src.agents"):
            raise ImportError("no agents in core repo")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    brain.reset_brain()
    with pytest.raises(brain.BrainNotConfigured):
        brain.get_brain()
