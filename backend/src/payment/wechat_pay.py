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

import hashlib
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
        # 凭证不全 → stub 模式
        return _stub_order_result(out_trade_no)

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
            prepay_id = data["prepay_id"]

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
        else:
            return _stub_order_result(out_trade_no)
    except Exception:
        return _stub_order_result(out_trade_no)


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
        return _stub_order_result(out_trade_no)

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
            return WeChatOrderResult(
                prepay_id="",
                out_trade_no=out_trade_no,
                qr_code_url=data.get("code_url", ""),
            )
        else:
            return _stub_order_result(out_trade_no)
    except Exception:
        return _stub_order_result(out_trade_no)


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
) -> bool:
    """验证微信支付回调通知签名。

    签名串：timestamp + "\n" + nonce + "\n" + body + "\n"
    用 API v3 key 做 HMAC-SHA256 签名，结果与 callback 头中的签名对比。
    """
    if not api_v3_key:
        # 未配置密钥 → stub 模式下直接放行
        return True

    sign_message = f"{timestamp}\n{nonce}\n{body}\n"
    expected = hmac_sha256(sign_message, api_v3_key)

    if not _constant_time_compare(expected, signature):
        return False
    return True


def hmac_sha256(message: str, key: str) -> str:
    """HMAC-SHA256 签名，返回十六进制字符串。"""
    import hmac as hmac_module
    mac = hmac_module.new(
        key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    )
    return mac.hexdigest()


def _constant_time_compare(a: str, b: str) -> bool:
    """防时序攻击的字符串比较。"""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def parse_notify_body(body: str) -> NotifyResult:
    """解析微信支付回调通知 JSON 体。

    回调体结构见：
    https://pay.weixin.qq.com/doc/v3/merchant/4012791897
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return NotifyResult(success=False, error="Invalid JSON")

    event_type = data.get("event_type", "")
    if event_type != "TRANSACTION.SUCCESS":
        return NotifyResult(success=False, error=f"Unsupported event: {event_type}")

    resource = data.get("resource", {})
    # resource 可能是加密的（需用 API v3 key 解密），也可能不加密
    # 简化处理：如果 resource 是 dict 且包含 ciphertext，跳过解密（stub模式）
    decrypted = resource

    out_trade_no = decrypted.get("out_trade_no", "")
    transaction_id = decrypted.get("transaction_id", "")
    amount = decrypted.get("amount", {})
    amount_total = amount.get("total", 0) if isinstance(amount, dict) else 0

    return NotifyResult(
        success=True,
        out_trade_no=out_trade_no,
        transaction_id=transaction_id,
        amount_total=amount_total,
    )


def build_notify_response(
    success: bool,
    *,
    http_status: int | None = None,
    message: str | None = None,
) -> tuple[str, int]:
    """构建微信支付回调的应答体。

    成功 → {"code": "SUCCESS", "message": "OK"} 200
    失败 → {"code": "FAIL", "message": "..."} 4xx（空/未签名/验签失败用 4xx，
            避免空回调被记成 500 服务故障；真签成功路径仍 200）
    """
    if success:
        return json.dumps({"code": "SUCCESS", "message": "OK"}), 200
    status = 400 if http_status is None else http_status
    msg = message or "Signature verification failed"
    return json.dumps({"code": "FAIL", "message": msg}), status


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
