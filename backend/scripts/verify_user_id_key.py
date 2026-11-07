# -*- coding: utf-8 -*-
"""Phase 1 键位负向断言：X-User-Id 与 token 不一致必须 403；一致 200；缺 token 401。

默认打宿主 :5200（HTTP 代理模式），也可传 base 直接打核 :5300。
"""
import json
import sys
import urllib.error
import urllib.request

B = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5200").rstrip("/")
EMAIL, PWD = "core-accept-1@sim.local", "Core-Accept-2026!"
fails = []


def call(path, method="GET", payload=None, token=None, uid_key=None, timeout=240):
    req = urllib.request.Request(B + path, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if uid_key:
        req.add_header("X-User-Id", uid_key)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    try:
        with urllib.request.urlopen(req, body, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw[:120]}


def check(name, ok, detail):
    print("%-28s %s %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        fails.append(name)


st, r = call("/v1/auth/login", "POST", {"email": EMAIL, "password": PWD}, timeout=30)
tok = r.get("access_token", "")
uid = (r.get("user") or {}).get("id", "")
check("login(base)", st == 200 and bool(tok), "status=%s uid=%s" % (st, uid))

# 1) 正确键位 → 200
st, a = call("/v1/ask", "POST", {"query": "键位一致校验 k1", "mode": "rag"}, tok, uid)
check("key.match→200", st == 200, "status=%s intent=%s" % (st, a.get("intent")))

# 2) 错配键位 → 403 user_id_mismatch（负向断言：必须失败）
st, a = call("/v1/ask", "POST", {"query": "键位错配校验 k2", "mode": "rag"}, tok, "00000000-0000-0000-0000-000000000001")
check("key.mismatch→403", st == 403 and a.get("error") == "user_id_mismatch",
      "status=%s error=%s token_user_id=%s" % (st, a.get("error"), a.get("token_user_id")))

# 3) 只带键位不带 token → 401
st, a = call("/v1/ask", "POST", {"query": "键位无token k3", "mode": "rag"}, None, uid)
check("key.without_token→401", st == 401, "status=%s error=%s" % (st, a.get("error")))

# 4) 不带键位（存量调用）→ 200，未破坏兼容
st, a = call("/v1/ask", "POST", {"query": "无键位兼容 k4", "mode": "rag"}, tok, None)
check("key.absent→200", st == 200, "status=%s intent=%s" % (st, a.get("intent")))

print("verdict: " + ("PASS" if not fails else "FAIL:" + ",".join(fails)))
sys.exit(0 if not fails else 1)
