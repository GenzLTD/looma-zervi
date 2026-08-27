"""Smoke: Sidecar tool surface stays one-MCP / many-tools (no QCC 1:1 mirror)."""
import importlib.util
from pathlib import Path


def _load_server():
    path = Path(__file__).resolve().parent / "server.py"
    spec = importlib.util.spec_from_file_location("looma_mcp_server", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_tool_names_product_shape():
    mod = _load_server()
    names = set(mod.TOOL_NAMES)
    # Aggregate + focused credit tools
    assert "credit_check" in names
    assert "credit_company" in names
    assert "credit_risk" in names
    assert "credit_legal" in names
    # Must NOT mirror QCC server ids as tool names
    for banned in (
        "qcc-company",
        "qcc-risk",
        "qcc-ipr",
        "qcc-operation",
        "qcc-executive",
        "qcc-history",
        "qcc-legal-regulation",
        "qcc-legal-case",
        "qcc-document",
    ):
        assert banned not in names
    health = mod.health_status()
    assert health["shape"] == "one_mcp_many_tools"
    assert set(health["tools"]) == names
    assert "/sse" in health.get("sse_url", "")
    html = mod._landing_html()
    assert "Looma MCP Sidecar" in html
    assert "credit_check" in html


if __name__ == "__main__":
    test_tool_names_product_shape()
    print("ok")
