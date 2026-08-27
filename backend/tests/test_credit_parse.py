"""Unit tests for credit JSON extraction / QCC error sanitization."""
from src.api.routes.credit_routes import _extract_json_object, _sanitize_qcc_error
from src.credit.qcc_client import QccMcpError


def test_extract_json_object_pure():
    data = _extract_json_object(
        '{"entity_name":"腾讯","report_type":"评估","summary":"存续"}'
    )
    assert data["entity_name"] == "腾讯"


def test_extract_json_object_from_prose_and_fence():
    prose = (
        "嗨，我是星际导航员。以下是结果：\n"
        "```json\n"
        '{"entity_name":"字节跳动","report_type":"经营风险评估","summary":"正常经营"}\n'
        "```\n"
        "还想继续探索吗？"
    )
    data = _extract_json_object(prose)
    assert data is not None
    assert data["entity_name"] == "字节跳动"
    assert "summary" in data


def test_extract_json_object_embedded_braces():
    text = '说明如下 {"entity_name":"阿里","report_type":"摘要","summary":"稳定"} 结束'
    data = _extract_json_object(text)
    assert data["entity_name"] == "阿里"


def test_sanitize_qcc_error_classes():
    assert _sanitize_qcc_error(QccMcpError("QCC_AUTH_TOKEN 未配置或为空")) == "token_missing"
    assert _sanitize_qcc_error(Exception("401 Unauthorized")) == "unauthorized"
    assert _sanitize_qcc_error(Exception("SSE connect failed")) == "unreachable"
    assert _sanitize_qcc_error(Exception("Read timeout")) == "timeout"
    assert (
        _sanitize_qcc_error(
            QccMcpError("[company] Failed to obtain SSE session ID (endpoint handshake)")
        )
        == "protocol_error"
    )


def test_get_qcc_base_urls_honours_gateway(monkeypatch):
    from src.credit import qcc_client as qc

    monkeypatch.setenv("QCC_MCP_BASE_URL", "http://1.14.202.161:8998/mcp")
    urls = qc.get_qcc_base_urls()
    assert urls["company"] == "http://1.14.202.161:8998/mcp/company/stream"
    assert urls["risk"].endswith("/mcp/risk/stream")


def test_parse_sse_rpc_result_helpers():
    from src.credit.qcc_client import QccMcpSession

    sess = QccMcpSession("company", "http://example/mcp/company/stream", "Bearer x")

    class _Resp:
        headers = {"Content-Type": "text/event-stream", "Mcp-Session-Id": "sess-1"}
        text = (
            'event: message\n'
            'data: {"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"search"}]}}\n\n'
        )

        def json(self):
            raise ValueError("not json")

    out = sess._parse_rpc_response(_Resp())  # type: ignore[arg-type]
    assert out["tools"][0]["name"] == "search"
    assert sess._session_id == "sess-1"


def test_parse_company_result_chinese_and_mojibake():
    from src.credit.qcc_client import _parse_company_result

    good = (
        '{"企业名称":"腾讯科技（深圳）有限公司","法定代表人":"马化腾",'
        '"统一社会信用代码":"9144030071526726XG","登记状态":"存续"}'
    )
    broken = good.encode("utf-8").decode("latin-1")
    info = _parse_company_result(
        {"content": [{"type": "text", "text": broken}]}
    )
    assert info.company_name == "腾讯科技（深圳）有限公司"
    assert info.legal_person == "马化腾"
    assert info.credit_code == "9144030071526726XG"
    assert info.status == "存续"
