"""Unit tests for Ask RAG mode presets (chat / deepseek / fast)."""
from src.agents.central_brain import (
    ASK_MODE_PRESETS,
    get_ask_mode_preset,
    resolve_ask_mode,
    _format_session_history,
)


def test_resolve_ask_mode_defaults_and_aliases():
    assert resolve_ask_mode(None) == "chat"
    assert resolve_ask_mode("CHAT") == "chat"
    assert resolve_ask_mode("deepseek") == "deepseek"
    assert resolve_ask_mode("fast") == "fast"
    assert resolve_ask_mode("unknown-mode") == "chat"


def test_presets_match_product_contract():
    chat = get_ask_mode_preset("chat")
    deep = get_ask_mode_preset("deepseek")
    fast = get_ask_mode_preset("fast")

    # 对话：多轮上下文
    assert chat["history_turns"] >= 8
    assert chat["top_k"] == 3

    # 深度：更大 top_k + 更长推理预算
    assert deep["top_k"] > chat["top_k"]
    assert deep["max_tokens"] > chat["max_tokens"]
    assert deep["reasoning"] is True

    # 快速：少检索 + 低温度 + 短答
    assert fast["top_k"] < chat["top_k"]
    assert fast["temperature"] < chat["temperature"]
    assert fast["history_turns"] == 0
    assert fast["max_tokens"] < chat["max_tokens"]


def test_all_presets_have_required_keys():
    required = {"top_k", "history_turns", "temperature", "max_tokens", "reasoning"}
    for name, preset in ASK_MODE_PRESETS.items():
        assert required <= set(preset.keys()), name


def test_format_session_history_respects_turns():
    history = [
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "第一答"},
        {"role": "user", "content": "第二问"},
        {"role": "assistant", "content": "第二答"},
    ]
    assert _format_session_history(history, 0) == ""
    block = _format_session_history(history, 2)
    assert "第二问" in block
    assert "第一问" not in block
    assert "[对话历史]" in block
