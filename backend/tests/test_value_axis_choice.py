"""Act 1 choice axis is the option axis, and the GFCC envelope refuses score fields."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.domain_engine import DomainEngine
from src.signal_bridge.gfcc_fanout import to_gfcc_value_axis_envelope

HASH_A = "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"


def test_career_reject_lands_on_freedom_not_survival():
    engine = DomainEngine()
    result = engine.add_imprint("user-1", "职业域", 3, axis="freedom")
    assert result["axis"] == "freedom"
    assert result["added"] == 3
    assert result["total"]["freedom"] == 3
    assert result["total"]["survival"] == 0
    assert result["total"]["belonging"] == 0


def test_value_axis_envelope_uses_the_option_axis():
    mapped = to_gfcc_value_axis_envelope(
        HASH_A, "freedom", "尊严", "职业域", 3, "nonce-axis-1",
    )
    payload = mapped["envelope"]["payload"]
    assert mapped["envelope"]["signal_type"] == "value_axis_choice"
    assert payload == {
        "axis": "freedom",
        "imprint_name": "尊严",
        "domain": "职业域",
        "points": 3,
        "source": "planetx",
    }
    assert "salary_match" not in payload


def test_value_axis_envelope_rejects_a_score_axis():
    mapped = to_gfcc_value_axis_envelope(
        HASH_A, "salary_match", "务实", "职业域", 3, "nonce-axis-2",
    )
    assert mapped["skip"] == "axis_invalid"
