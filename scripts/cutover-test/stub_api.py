#!/usr/bin/env python3
"""摘块预演用的最小 backend stub（顶替 Flask :5200）。

只做三件事：
  1. `GET /health` 返回 200 —— 证明 api 反代链路还在；
  2. webhook 家族返回 200 —— 证明 Stripe / WeChat 收银路径没被摘掉；
  3. 其余 `/v1/*` 返回 200 stub —— 让"路径是否可达"与"业务是否正确"解耦。

刻意**不**实现任何业务逻辑、不连数据库、不校验签名。这是路由门禁，不是功能测试。

用法：
    python3 stub_api.py [--port 15200]

无第三方依赖（仅标准库），macOS / Linux / Windows 通用。
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# webhook 家族：这些路径一旦被 nginx 摘块误伤，收银就断了，必须逐个 200
WEBHOOK_PREFIXES = (
    "/v1/payment/webhook/",        # 统一接收器（stripe / paypal / airwallex）
    "/v1/payment/stripe/webhook",  # 历史兼容路径
    "/v1/payment/wechat/notify",   # 微信支付回调
)


class StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "looma-cutover-stub"

    # ------------------------------------------------------------------ 工具
    def _send(self, code: int, payload: dict, ctype: str = "application/json") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _log(self, note: str = "") -> None:
        # 带 Host 的访问日志：预演没它就没法证明"哪个 Host 命中哪个 server 块"
        host = self.headers.get("Host", "-")
        print(f"[stub] {self.command} {self.path}  host={host} {note}", flush=True)

    # ------------------------------------------------------------------ 路由
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        self._log()

        if path == "/health":
            self._send(200, {
                "service": "looma-backend-stub",
                "status": "ok",
                "version": "cutover-test",
            })
            return

        if path == "/":
            # 真 Flask 根路径返回端点清单；stub 保持 200 JSON，便于区分
            # "nginx 把请求转给了 backend" 与 "nginx 自己 404 了"
            self._send(200, {
                "service": "looma-backend-stub",
                "endpoints": ["/health", "/v1/*"],
                "note": "cutover-test stub",
            })
            return

        if path.startswith("/v1/"):
            self._send(200, {"stub": True, "method": "GET", "path": path})
            return

        self._send(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""

        is_webhook = any(path.startswith(p) for p in WEBHOOK_PREFIXES)
        self._log("WEBHOOK" if is_webhook else "")

        if is_webhook:
            # 真实现会验签 + 落库；stub 只证明路径可达。
            provider = "unknown"
            for name in ("stripe", "paypal", "airwallex", "wechat"):
                if name in path:
                    provider = name
                    break
            self._send(200, {
                "received": True,
                "provider": provider,
                "stub": True,
                "bytes": len(raw),
            })
            return

        if path.startswith("/v1/"):
            self._send(200, {"stub": True, "method": "POST", "path": path})
            return

        self._send(404, {"error": "not_found", "path": path})

    def do_HEAD(self) -> None:  # noqa: N802
        self._send(200, {})

    def log_message(self, fmt: str, *args) -> None:  # 静音默认日志，只留 _log
        return


def main() -> int:
    ap = argparse.ArgumentParser(description="cutover-test backend stub")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=15200)
    args = ap.parse_args()

    srv = ThreadingHTTPServer((args.host, args.port), StubHandler)
    print(f"[stub] listening on http://{args.host}:{args.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[stub] interrupted", flush=True)
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
