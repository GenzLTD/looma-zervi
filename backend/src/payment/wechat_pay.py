"""
WeChat Pay API v3 集成骨架。

支持两种支付方式：
  - JSAPI 支付（微信浏览器/小程序内唤起）
  - Native 支付（PC 端扫码支付）

生产环境需配置以下环境变量：
  - WECHAT_MCHID            商户号
  - WECHAT_APPID            公众号/小程序 AppID（若与登录共用则复用 WECHAT_APPID）
  - WECHAT_API_V3_KEY       API v3 密钥（32 位）
  - WECHAT_SERIAL_NO        商户 API 证书序列号
  - WECHAT_PRIVATE_KEY_PATH 商户 API 私钥文件路径（PEM 格式）
  - WECHAT_NOTIFY_URL       支付结果通知 URL

参考文档：https://pay.weixin.qq.com/doc/v3/merchant/4012791856

Ownership: szbenyx (与 szbolent-portal 支付共用契约)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import requests

# ---------- WeChat Pay API v3 endpoint ----------
WECHAT_API_BASE = "https://api.mch.weixin.qq.com"
WECHAT_JSAPI_ORDER = "/v3/pay/transactions/jsapi"
WECHAT_NATIVE_ORDER = "/v3/pay/transactions/native"
WECHAT_H5_ORDER = "/v3/pay/transactions/h5"
WECHAT_ORDER_QUERY = "/v3/pay/transactions/out-trade-no/{out_trade_no}"
WECHAT_REFUND = "/v3/refund/domestic/refunds"

# 回调通知头字段名
WECHAT_SIGNATURE_HEADER = "Wechatpay-Signature"
WECHAT_SERIAL_HEADER = "Wechatpay-Serial"
WECHAT_TIMESTAMP_HEADER = "Wechatpay-Timestamp"
WECHAT_NONCE_HEADER = "Wechatpay-Nonce"


@dataclass
class WeChatOrderResult:
    """统一下单返回结果（JSAPI/Native/H5 共用）"""

    prepay_id: str
    out_trade_no: str
    # JSAPI 支付参数（前端 wx.chooseWXPay 需要）
    jsapi_package: str = ""       # "prepay_id=wx..."
    jsapi_pay_sign: str = ""
    jsapi_nonce_str: str = ""
    jsapi_time_stamp: str = ""
    # Native 支付参数
    qr_code_url: str = ""
    # H5 支付参数
    h5_url: str = ""
    # 非空表示下单失败。生产路径不得把失败伪装成 stub prepay。
    error: str = ""


@dataclass
class NotifyResult:
    """支付通知处理结果"""

    success: bool
    out_trade_no: str = ""
    transaction_id: str = ""
    amount_total: int = 0        # 单位：分
    error: str = ""


# ============================================================
# 签名工具
# ============================================================

def _load_private_key(path: str) -> Optional[str]:
    """加载商户私钥（PEM 格式）。"""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception:
        return None


def _sign_rsa_sha256(message: str, private_key_pem: str) -> str:
    """对消息做 SHA256-RSA2048 签名，返回 base64 编码的签名值。"""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64

        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None, backend=default_backend()
        )
        signature = private_key.sign(
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")
    except ImportError:
        # cryptography 未安装时回退到 stub 签名
        return "stub_signature_no_cryptography"


def _build_authorization(
    mchid: str, serial_no: str, private_key_pem: str,
    method: str, url_path: str, body: str,
) -> str:
    """构造 WeChat Pay API v3 的 Authorization 头。

    格式：WECHATPAY2-SHA256-RSA2048 mchid="...",nonce_str="...",
          signature="...",timestamp="...",serial_no="..."
    """
    nonce_str = uuid.uuid4().hex[:32]
    timestamp = str(int(time.time()))

    # 签名串：method + "\n" + url_path + "\n" + timestamp + "\n" + nonce_str + "\n" + body + "\n"
    sign_message = f"{method.upper()}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"
    signature = _sign_rsa_sha256(sign_message, private_key_pem)

    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",'
        f'nonce_str="{nonce_str}",'
        f'signature="{signature}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{serial_no}"'
    )


# ============================================================
# 统一下单
# ============================================================

def create_jsapi_order(
    mchid: str,
    appid: str,
    openid: str,
    description: str,
    out_trade_no: str,
    amount_total: int,       # 单位：分（1 元 = 100）
    notify_url: str,
    api_v3_key: str = "",
    serial_no: str = "",
    private_key_path: str = "",
) -> WeChatOrderResult:
    """创建 JSAPI 订单（适用于微信内浏览器 / 小程序）。

    返回 prepay_id 用于前端 wx.chooseWXPay 唤起支付。
    """
    body = json.dumps({
        "appid": appid,
        "mchid": mchid,
        "description": description,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "amount": {
            "total": amount_total,
            "currency": "CNY",
        },
        "payer": {
            "openid": openid,
        },
    })

    private_key_pem = _load_private_key(private_key_path)
    if not private_key_pem or not api_v3_key or not serial_no:
        return _failed_order(out_trade_no, "WeChat Pay credentials incomplete")

    auth = _build_authorization(mchid, serial_no, private_key_pem, "POST", WECHAT_JSAPI_ORDER, body)
    try:
        resp = requests.post(
            f"{WECHAT_API_BASE}{WECHAT_JSAPI_ORDER}",
            data=body.encode("utf-8"),
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "looma-backend/1.0",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            prepay_id = data.get("prepay_id") or ""
            if not prepay_id:
                return _failed_order(out_trade_no, "WeChat response missing prepay_id")

            # 生成 JSAPI 前端调起支付所需的签名
            jsapi_package = f"prepay_id={prepay_id}"
            nonce_str = uuid.uuid4().hex[:32]
            time_stamp = str(int(time.time()))
            sign_message = f"{appid}\n{time_stamp}\n{nonce_str}\n{jsapi_package}\n"
            pay_sign = _sign_rsa_sha256(sign_message, private_key_pem)

            return WeChatOrderResult(
                prepay_id=prepay_id,
                out_trade_no=out_trade_no,
                jsapi_package=jsapi_package,
                jsapi_pay_sign=pay_sign,
                jsapi_nonce_str=nonce_str,
                jsapi_time_stamp=time_stamp,
            )
        return _failed_order(
            out_trade_no, f"WeChat order rejected: HTTP {resp.status_code}"
        )
    except Exception as exc:
        return _failed_order(out_trade_no, f"WeChat order failed: {type(exc).__name__}")


def create_native_order(
    mchid: str,
    appid: str,
    description: str,
    out_trade_no: str,
    amount_total: int,
    notify_url: str,
    api_v3_key: str = "",
    serial_no: str = "",
    private_key_path: str = "",
) -> WeChatOrderResult:
    """创建 Native 支付订单（PC 端扫码支付）。

    返回 qr_code_url 用于前端生成二维码。
    """
    body = json.dumps({
        "appid": appid,
        "mchid": mchid,
        "description": description,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "amount": {
            "total": amount_total,
            "currency": "CNY",
        },
    })

    private_key_pem = _load_private_key(private_key_path)
    if not private_key_pem or not api_v3_key or not serial_no:
        return _failed_order(out_trade_no, "WeChat Pay credentials incomplete")

    auth = _build_authorization(mchid, serial_no, private_key_pem, "POST", WECHAT_NATIVE_ORDER, body)
    try:
        resp = requests.post(
            f"{WECHAT_API_BASE}{WECHAT_NATIVE_ORDER}",
            data=body.encode("utf-8"),
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "looma-backend/1.0",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            code_url = data.get("code_url") or ""
            if not code_url:
                return _failed_order(out_trade_no, "WeChat response missing code_url")
            return WeChatOrderResult(
                prepay_id="",
                out_trade_no=out_trade_no,
                qr_code_url=code_url,
            )
        return _failed_order(
            out_trade_no, f"WeChat order rejected: HTTP {resp.status_code}"
        )
    except Exception as exc:
        return _failed_order(out_trade_no, f"WeChat order failed: {type(exc).__name__}")


def _failed_order(out_trade_no: str, error: str) -> WeChatOrderResult:
    """生产下单失败。调用方看到 error 后应返回 5xx，不得落一笔假 prepay。"""
    return WeChatOrderResult(prepay_id="", out_trade_no=out_trade_no, error=error)


def _stub_order_result(out_trade_no: str) -> WeChatOrderResult:
    """Stub 模式返回模拟结果（开发/测试用）。"""
    return WeChatOrderResult(
        prepay_id=f"stub_prepay_{out_trade_no[-12:]}",
        out_trade_no=out_trade_no,
        jsapi_package=f"prepay_id=stub_prepay_{out_trade_no[-12:]}",
        jsapi_pay_sign="STUB_SIGN",
        jsapi_nonce_str=uuid.uuid4().hex[:32],
        jsapi_time_stamp=str(int(time.time())),
        qr_code_url="stub://qr_code",
    )


# ============================================================
# 通知回调验签
# ============================================================

def verify_notify_sign(
    body: str,
    signature: str,
    serial_no: str,
    timestamp: str,
    nonce: str,
    api_v3_key: str = "",
    public_keys: Optional[dict] = None,
    allow_unsigned: bool = False,
) -> bool:
    """验证微信支付回调通知签名。

    生产路径：消息为 timestamp\\n + nonce\\n + body\\n，签名是请求头里
    Base64 的 RSA-SHA256。公钥按 Wechatpay-Serial 选取（微信支付公钥或平台证书）。
    api_v3_key 不参与验签，只留给报文解密。

    allow_unsigned 只给 PAYMENT_STUB_MODE。空密钥不再放行。
    """
    del api_v3_key  # 解密用，验签不用
    if allow_unsigned:
        return True
    if not signature or not serial_no or not timestamp or not nonce:
        return False
    pem = (public_keys or {}).get(serial_no)
    if not pem:
        return False
    message = f"{timestamp}\n{nonce}\n{body}\n"
    return _verify_rsa_sha256(message, signature, pem)


def _verify_rsa_sha256(message: str, signature_b64: str, pem: str) -> bool:
    """用证书或公钥 PEM 校验 PKCS1v15 SHA256 签名。"""
    try:
        import base64

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.x509 import load_pem_x509_certificate

        raw = pem.encode("utf-8") if isinstance(pem, str) else pem
        if b"BEGIN CERTIFICATE" in raw:
            public_key = load_pem_x509_certificate(raw).public_key()
        else:
            public_key = serialization.load_pem_public_key(raw)
        public_key.verify(
            base64.b64decode(signature_b64),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def _api_v3_key_bytes(api_v3_key: str) -> bytes:
    key = (api_v3_key or "").encode("utf-8")
    if len(key) != 32:
        raise ValueError("API v3 key must be 32 bytes")
    return key


def encrypt_aes_gcm(
    api_v3_key: str, nonce: str, plaintext: bytes, associated_data: str = ""
) -> str:
    """AEAD_AES_256_GCM，返回 Base64。测试和证书夹具用。"""
    import base64

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aad = associated_data.encode("utf-8")
    ciphertext = AESGCM(_api_v3_key_bytes(api_v3_key)).encrypt(
        nonce.encode("utf-8"), plaintext, aad
    )
    return base64.b64encode(ciphertext).decode("ascii")


def decrypt_aes_gcm(
    api_v3_key: str, nonce: str, ciphertext_b64: str, associated_data: str = ""
) -> bytes:
    """解密微信支付 resource 或平台证书。失败抛出异常，不返回明文残片。"""
    import base64

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aad = associated_data.encode("utf-8")
    return AESGCM(_api_v3_key_bytes(api_v3_key)).decrypt(
        nonce.encode("utf-8"), base64.b64decode(ciphertext_b64), aad
    )


def encrypt_resource(
    api_v3_key: str,
    payload: dict,
    nonce: str,
    associated_data: str = "transaction",
) -> dict:
    """把交易明文包成回调里的 resource 对象。"""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return {
        "algorithm": "AEAD_AES_256_GCM",
        "ciphertext": encrypt_aes_gcm(api_v3_key, nonce, raw, associated_data),
        "nonce": nonce,
        "associated_data": associated_data,
    }


def certificates_from_download(api_v3_key: str, payload: dict) -> dict:
    """解开 GET /v3/certificates 的响应，得到 serial -> PEM。"""
    found = {}
    for item in payload.get("data") or []:
        enc = item.get("encrypt_certificate") or {}
        if enc.get("algorithm") not in (None, "", "AEAD_AES_256_GCM"):
            raise ValueError(f"unsupported certificate algorithm: {enc.get('algorithm')}")
        pem = decrypt_aes_gcm(
            api_v3_key,
            enc.get("nonce") or "",
            enc.get("ciphertext") or "",
            enc.get("associated_data") or "",
        ).decode("utf-8")
        serial = item.get("serial_no") or ""
        if not serial or "BEGIN CERTIFICATE" not in pem:
            raise ValueError("platform certificate payload missing serial or PEM")
        found[serial] = pem
    if not found:
        raise ValueError("platform certificate list is empty")
    return found


def load_notify_public_keys(config: dict) -> dict:
    """按序列号收集验签材料。不访问微信。

    WECHAT_PAY_PUBLIC_KEY_ID + WECHAT_PAY_PUBLIC_KEY_PATH：商户平台的微信支付公钥。
    WECHAT_PLATFORM_CERT_DIR：文件名即序列号的 PEM（平台证书轮换后的本地缓存）。
    """
    keys: dict[str, str] = {}
    key_id = str(config.get("WECHAT_PAY_PUBLIC_KEY_ID") or "").strip()
    key_path = str(config.get("WECHAT_PAY_PUBLIC_KEY_PATH") or "").strip()
    if key_id and key_path and os.path.isfile(key_path):
        with open(key_path, "r") as handle:
            keys[key_id] = handle.read()
    cert_dir = str(config.get("WECHAT_PLATFORM_CERT_DIR") or "").strip()
    if cert_dir and os.path.isdir(cert_dir):
        for name in os.listdir(cert_dir):
            if not name.endswith(".pem"):
                continue
            with open(os.path.join(cert_dir, name), "r") as handle:
                keys[name[:-4]] = handle.read()
    return keys


def parse_notify_body(
    body: str, api_v3_key: str = "", allow_plaintext: bool = False
) -> NotifyResult:
    """解析微信支付回调通知 JSON 体。

    生产回调的 resource 是 AEAD_AES_256_GCM。解密失败即失败，不把密文当明文。
    allow_plaintext 只给 PAYMENT_STUB_MODE 的联调夹具。
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return NotifyResult(success=False, error="Invalid JSON")

    event_type = data.get("event_type", "")
    if event_type != "TRANSACTION.SUCCESS":
        return NotifyResult(success=False, error=f"Unsupported event: {event_type}")

    resource = data.get("resource") or {}
    if not isinstance(resource, dict):
        return NotifyResult(success=False, error="resource is not an object")

    if resource.get("ciphertext"):
        algorithm = resource.get("algorithm") or "AEAD_AES_256_GCM"
        if algorithm != "AEAD_AES_256_GCM":
            return NotifyResult(success=False, error=f"Unsupported algorithm: {algorithm}")
        try:
            raw = decrypt_aes_gcm(
                api_v3_key,
                resource.get("nonce") or "",
                resource.get("ciphertext") or "",
                resource.get("associated_data") or "",
            )
            decrypted = json.loads(raw.decode("utf-8"))
        except Exception:
            return NotifyResult(success=False, error="resource decrypt failed")
    elif allow_plaintext:
        decrypted = resource
    else:
        return NotifyResult(success=False, error="encrypted resource required")

    if not isinstance(decrypted, dict):
        return NotifyResult(success=False, error="decrypted resource is not an object")

    out_trade_no = decrypted.get("out_trade_no") or ""
    if not out_trade_no:
        return NotifyResult(success=False, error="missing out_trade_no")
    transaction_id = decrypted.get("transaction_id") or ""
    amount = decrypted.get("amount") or {}
    amount_total = amount.get("total", 0) if isinstance(amount, dict) else 0

    return NotifyResult(
        success=True,
        out_trade_no=out_trade_no,
        transaction_id=transaction_id,
        amount_total=amount_total,
    )


def build_notify_response(success: bool) -> tuple[str, int]:
    """构建微信支付回调的应答体。

    成功 → {"code": "SUCCESS", "message": "OK"} 200
    失败 → {"code": "FAIL", "message": "..."}     500
    """
    if success:
        return json.dumps({"code": "SUCCESS", "message": "OK"}), 200
    else:
        return json.dumps({"code": "FAIL", "message": "Signature verification failed"}), 500


# ============================================================
# 生成 out_trade_no
# ============================================================

def generate_out_trade_no() -> str:
    """生成唯一商户订单号。

    格式：LOOMA + YYYYMMDDHHmmss + 8位随机hex
    示例：LOOMA20260711143022a1b2c3d4
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:8].upper()
    return f"LOOMA{ts}{rand}"
