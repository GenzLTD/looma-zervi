"""Tests for Compliance Gate modules."""
from unittest.mock import MagicMock

from src.compliance.consent import ConsentManager, ALL_SCOPES
from src.compliance.redact import redact_pii, detect_pii
from src.compliance.audit import AuditLogger, _anonymize_ip


class TestConsentManager:
    def test_grant_new(self):
        db = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        db.get_conn.return_value.__enter__.return_value = conn
        cm = ConsentManager(db=db)
        r = cm.grant("user-1", "resume_upload")
        assert r["already_granted"] is False
        assert r["consent_id"]

    def test_grant_duplicate(self):
        db = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"id": "ex1"}
        db.get_conn.return_value.__enter__.return_value = conn
        cm = ConsentManager(db=db)
        r = cm.grant("user-1", "resume_upload")
        assert r["already_granted"] is True

    def test_check_true(self):
        db = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"id": "c1"}
        db.get_conn.return_value.__enter__.return_value = conn
        cm = ConsentManager(db=db)
        assert cm.check("user-1", "resume_upload") is True

    def test_check_false(self):
        db = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        db.get_conn.return_value.__enter__.return_value = conn
        cm = ConsentManager(db=db)
        assert cm.check("user-1", "credit_query") is False

    def test_check_false_unknown_scope(self):
        cm = ConsentManager(db=MagicMock())
        assert cm.check("user-1", "invalid_scope") is False

    def test_revoke(self):
        db = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"id": "c1"}
        db.get_conn.return_value.__enter__.return_value = conn
        cm = ConsentManager(db=db)
        r = cm.revoke("user-1", "resume_upload")
        assert r["revoked"] is True

    def test_all_scopes_count(self):
        # 3 primary tiers + 10 fine-grained / legacy scopes (incl. application_submit)
        assert len(ALL_SCOPES) == 13
        assert {"jobseeker_core", "credit_query", "report_share", "application_submit"} <= ALL_SCOPES


class TestRedaction:
    def test_redact_mobile(self):
        safe, reds = redact_pii("联系电话13812345678")
        assert "13812345678" not in safe
        assert "[PII_PHONE_" in safe
        assert len(reds) >= 1  # at minimum phone, name may also match

    def test_redact_cn_name(self):
        text = "我叫张三，请帮我看看简历"
        safe, reds = redact_pii(text)
        assert "张三" not in safe
        assert "PII_NAME_" in safe
        assert len(reds) >= 1

    def test_redact_name_and_mobile(self):
        safe, reds = redact_pii("我叫张三，手机号13812345678")
        assert "13812345678" not in safe
        assert "张三" not in safe
        assert len(reds) >= 2

    def test_redact_email(self):
        safe, reds = redact_pii("邮箱：zhangsan@example.com")
        assert "zhangsan@example.com" not in safe
        assert "[PII_EMAIL_" in safe

    def test_no_pii(self):
        safe, reds = redact_pii("今天天气真好")
        assert safe == "今天天气真好"
        assert len(reds) == 0

    def test_detect_pii(self):
        findings = detect_pii("电话13800001111")
        assert any(f["type"] == "cn_mobile" for f in findings)

    def test_detect_id_card(self):
        findings = detect_pii("身份证 110101199001011234")
        assert any(f["type"] == "cn_id_card" for f in findings)


class TestAuditLogger:
    def test_log(self):
        db = MagicMock()
        conn = MagicMock()
        db.get_conn.return_value.__enter__.return_value = conn
        audit = AuditLogger(db=db)
        eid = audit.log(actor="user-1", action="resume_parse", resource_type="resume")
        assert eid
        conn.execute.assert_called_once()

    def test_log_no_db(self):
        audit = AuditLogger(db=None)
        assert audit.log(actor="u1", action="x", resource_type="y") == ""


class TestIPAnonymization:
    def test_mask_last_octet(self):
        assert _anonymize_ip("192.168.1.100") == "192.168.1.0"

    def test_localhost(self):
        assert _anonymize_ip("127.0.0.1") == "127.0.0.0"

    def test_malformed(self):
        assert _anonymize_ip("not-an-ip") == ""
