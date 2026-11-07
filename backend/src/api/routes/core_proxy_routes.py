"""核反代蓝图（Phase 1，`THOMAS_CORE_MODE=http` 时启用）。

宿主不再把 auth / ask / compliance 三核蓝图装进自己的进程，而是把这三组路径
原样转发给核进程（默认 `http://127.0.0.1:5300`）——这条通路就是 Phase 1
要验的「product → core 跨进程调用」。

保留：方法、query string、Content-Type、Authorization、**X-User-Id**（R1 键位）、
状态码与响应体。核不可达时返回 502 `core_unreachable`，不吞成 500。
"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from src.thomas_core import client

core_proxy_bp = Blueprint("core_proxy", __name__)

_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def _proxy(path: str):
    headers = {h: request.headers.get(h) for h in client.FORWARD_HEADERS}
    body = request.get_data() or None
    query = request.query_string.decode("utf-8", "replace")
    try:
        status, payload, ctype = client.forward(request.method, path, body, headers, query)
    except Exception as exc:  # CoreUnreachable / URLError / timeout
        return (
            jsonify(
                error="core_unreachable",
                message=str(exc),
                core_url=client.base_url(),
                hint="核进程是否运行？backend/run_core.py（:5300）",
            ),
            502,
        )
    return Response(payload, status=status, content_type=ctype)


@core_proxy_bp.route("/v1/auth/<path:sub>", methods=_METHODS)
def proxy_auth(sub: str):
    return _proxy("/v1/auth/" + sub)


@core_proxy_bp.route("/v1/ask", methods=_METHODS)
def proxy_ask():
    return _proxy("/v1/ask")


@core_proxy_bp.route("/v1/compliance/<path:sub>", methods=_METHODS)
def proxy_compliance(sub: str):
    return _proxy("/v1/compliance/" + sub)
