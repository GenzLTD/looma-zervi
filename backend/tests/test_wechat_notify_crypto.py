"""Production WeChat notify crypto. These cases do not use the stub bypass."""
import base64
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from src.app import create_app
from src.payment import wechat_pay
from src.payment.wechat_pay import (
    certificates_from_download,
    create_jsapi_order,
    encrypt_aes_gcm,
    encrypt_resource,
    load_notify_public_keys,
    parse_notify_body,
    verify_notify_sign,
)

API_V3_KEY = "32byteslongsecretkeyforwechatpay"


def _keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, public_pem


def _sign(private_key, message: str) -> str:
    raw = private_key.sign(
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(raw).decode("ascii")


def _self_signed_pem(private_key) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wechat-platform-test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(0xA1B2C3)
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    return format(cert.serial_number, "X"), pem


def test_rsa_verify_accepts_matching_serial_and_rejects_tamper():
    private_key, public_pem = _keypair()
    body = '{"event_type":"TRANSACTION.SUCCESS"}'
    message = f"1700000000\nnonce12bytes\n{body}\n"
    signature = _sign(private_key, message)
    keys = {"PUB_KEY_ID_TEST": public_pem}

    assert verify_notify_sign(
        body, signature, "PUB_KEY_ID_TEST", "1700000000", "nonce12bytes",
        api_v3_key=API_V3_KEY, public_keys=keys,
    )
    assert not verify_notify_sign(
        body + " ", signature, "PUB_KEY_ID_TEST", "1700000000", "nonce12bytes",
        public_keys=keys,
    )
    assert not verify_notify_sign(
        body, signature, "OTHER", "1700000000", "nonce12bytes",
        public_keys=keys,
    )


def test_empty_key_does_not_accept_an_unsigned_production_callback():
    assert not verify_notify_sign("{}", "", "", "", "", api_v3_key="")
    assert verify_notify_sign("{}", "", "", "", "", allow_unsigned=True)


def test_aes_gcm_roundtrip_and_bad_key():
    nonce = "nonce12bytes"
    ciphertext = encrypt_aes_gcm(API_V3_KEY, nonce, b'{"out_trade_no":"LOOMA1"}', "transaction")
    plain = wechat_pay.decrypt_aes_gcm(API_V3_KEY, nonce, ciphertext, "transaction")
    assert json.loads(plain)["out_trade_no"] == "LOOMA1"
    with pytest.raises(Exception):
        wechat_pay.decrypt_aes_gcm("another-32-byte-api-v3-key!!!!", nonce, ciphertext, "transaction")
    with pytest.raises(Exception):
        wechat_pay.decrypt_aes_gcm(API_V3_KEY, "wrong-nonce!", ciphertext, "transaction")


def test_parse_decrypts_resource_and_rejects_plaintext_in_production():
    payload = {
        "out_trade_no": "LOOMA_CRYPTO_1",
        "transaction_id": "TXN1",
        "amount": {"total": 990},
    }
    body = json.dumps({
        "event_type": "TRANSACTION.SUCCESS",
        "resource": encrypt_resource(API_V3_KEY, payload, "nonce12bytes"),
    })
    parsed = parse_notify_body(body, api_v3_key=API_V3_KEY)
    assert parsed.success
    assert parsed.out_trade_no == "LOOMA_CRYPTO_1"
    assert parsed.transaction_id == "TXN1"
    assert parsed.amount_total == 990

    wrong = parse_notify_body(body, api_v3_key="another-32-byte-api-v3-key!!!!")
    assert not wrong.success

    plaintext = json.dumps({
        "event_type": "TRANSACTION.SUCCESS",
        "resource": payload,
    })
    assert not parse_notify_body(plaintext, api_v3_key=API_V3_KEY).success
    assert parse_notify_body(plaintext, allow_plaintext=True).success


def test_platform_certificate_download_payload_can_verify():
    private_key, _public_pem = _keypair()
    serial, cert_pem = _self_signed_pem(private_key)
    payload = {
        "data": [{
            "serial_no": serial,
            "encrypt_certificate": {
                "algorithm": "AEAD_AES_256_GCM",
                "nonce": "nonce12bytes",
                "associated_data": "certificate",
                "ciphertext": encrypt_aes_gcm(API_V3_KEY, "nonce12bytes", cert_pem.encode(), "certificate"),
            },
        }]
    }
    certs = certificates_from_download(API_V3_KEY, payload)
    body = "{}"
    message = f"1700000001\nabc\n{body}\n"
    signature = _sign(private_key, message)
    assert verify_notify_sign(
        body, signature, serial, "1700000001", "abc", public_keys=certs,
    )


def test_load_notify_public_keys_reads_id_and_cert_dir(tmp_path):
    private_key, public_pem = _keypair()
    pub_path = tmp_path / "pub.pem"
    pub_path.write_text(public_pem)
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    _serial, cert_pem = _self_signed_pem(private_key)
    (cert_dir / "PLATFORM123.pem").write_text(cert_pem)

    found = load_notify_public_keys({
        "WECHAT_PAY_PUBLIC_KEY_ID": "PUB_KEY_ID_TEST",
        "WECHAT_PAY_PUBLIC_KEY_PATH": str(pub_path),
        "WECHAT_PLATFORM_CERT_DIR": str(cert_dir),
    })
    assert "BEGIN PUBLIC KEY" in found["PUB_KEY_ID_TEST"]
    assert "BEGIN CERTIFICATE" in found["PLATFORM123"]


def test_jsapi_rejection_is_not_a_stub_prepay(tmp_path, monkeypatch):
    private_key, _public_pem = _keypair()
    key_path = tmp_path / "apiclient_key.pem"
    key_path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))

    class _Response:
        status_code = 400

        def json(self):
            return {"code": "PARAM_ERROR"}

    monkeypatch.setattr(wechat_pay.requests, "post", lambda *args, **kwargs: _Response())
    result = create_jsapi_order(
        mchid="1234567890",
        appid="wx_test",
        openid="openid",
        description="Looma",
        out_trade_no="LOOMA_FAIL_1",
        amount_total=990,
        notify_url="https://example.com/notify",
        api_v3_key=API_V3_KEY,
        serial_no="MERCHANT",
        private_key_path=str(key_path),
    )
    assert result.error.startswith("WeChat order rejected")
    assert result.prepay_id == ""


def test_production_route_rejects_unsigned_and_accepts_signed(tmp_path, monkeypatch):
    private_key, public_pem = _keypair()
    pub_path = tmp_path / "pub.pem"
    pub_path.write_text(public_pem)
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("JWT_SECRET", "test-secret-32bytes-long-enough!!")
    monkeypatch.setenv("PAYMENT_STUB_MODE", "false")
    monkeypatch.setenv("WECHAT_DEV_MODE", "true")
    monkeypatch.setenv("WECHAT_API_V3_KEY", API_V3_KEY)
    monkeypatch.setenv("WECHAT_PAY_PUBLIC_KEY_ID", "PUB_KEY_ID_TEST")
    monkeypatch.setenv("WECHAT_PAY_PUBLIC_KEY_PATH", str(pub_path))
    app = create_app("testing")
    client = app.test_client()

    denied = client.post("/v1/payment/wechat/notify", data="{}", content_type="application/json")
    assert denied.status_code == 500

    reg = client.post(
        "/v1/auth/register",
        json={"email": "crypto_route@test.com", "password": "secret123", "name": "Test"},
    )
    assert reg.status_code == 201
    user = reg.get_json()["user"]
    out_trade_no = "LOOMA_ROUTE_CRYPTO_1"
    app._db.create_order(
        user_id=user["id"],
        plan_id="supporter_cn",
        tier="supporter",
        amount=9.9,
        currency="CNY",
        out_trade_no=out_trade_no,
    )
    body = json.dumps({
        "event_type": "TRANSACTION.SUCCESS",
        "resource": encrypt_resource(
            API_V3_KEY,
            {
                "out_trade_no": out_trade_no,
                "transaction_id": "TXN_ROUTE",
                "amount": {"total": 990},
            },
            "nonce12bytes",
        ),
    })
    signature = _sign(private_key, f"1700000002\nnonce12bytes\n{body}\n")
    accepted = client.post(
        "/v1/payment/wechat/notify",
        data=body,
        content_type="application/json",
        headers={
            "Wechatpay-Timestamp": "1700000002",
            "Wechatpay-Nonce": "nonce12bytes",
            "Wechatpay-Signature": signature,
            "Wechatpay-Serial": "PUB_KEY_ID_TEST",
        },
    )
    assert accepted.status_code == 200
    assert json.loads(accepted.get_data(as_text=True))["code"] == "SUCCESS"
    assert app._db.get_user_by_id(user["id"])["tier"] == "supporter"
    os.unlink(db_path)
