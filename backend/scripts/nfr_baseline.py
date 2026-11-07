# -*- coding: utf-8 -*-
"""NFR 基线采集（对应验证链路 §12.6 第 4 项 / §13.5「未证」清单最后一项）。

只做**测量与统计**，不改任何业务代码、不改开关默认值、不写业务表（consent 是幂等 grant）。
输出：控制台 Markdown 表 + 可选 JSON（`--out`）。

测什么
------
1. **顺序延迟**：`/health`（纯框架）、`/v1/auth/profile`（鉴权 + DB 读）、
   `/v1/compliance/consent/grant`（鉴权 + DB 写）→ p50 / p95 / p99 / min / max。
2. **并发档位**：同一端点按 1/2/4/8/16/32 并发各打固定条数 → QPS、p95、错误数，
   用来看吞吐拐点（Werkzeug dev server + SQLite 串行化是已知上限来源）。
3. **ask 端到端 token 成本**：每轮带 nonce（绕开答案缓存，否则 `tokens_used=None`），
   记录 `tokens_used` 与耗时；给了单价才算钱。

怎么用（`backend/` 下，bash）
----------------------------
    ./.venv/Scripts/python.exe scripts/nfr_baseline.py \
        --url core-fast=http://127.0.0.1:5301 \
        --url core-debug=http://127.0.0.1:5300 \
        --url host=http://127.0.0.1:5200 \
        --health-rounds 120 --auth-rounds 60 --consent-rounds 40 \
        --ask-rounds 8 --levels 1,2,4,8,16,32 --per-level 200 \
        --out .tmp-nfr/nfr.json

口径纪律（别把这份数字当生产基线）
--------------------------------
- 客户端用 `http.client` **长连接**（keep-alive），所以数字里不含每次 TCP 建连的固定成本；
  但仍与被测端同机 —— 测的是"服务端处理 + 本机回环"，不含真实网络 RTT。
- 被测进程用 `app.run()`（Werkzeug dev server，threaded），**不是** gunicorn/waitress；
  `core-fast`（`debug=False`）只是把 dev server 的 debug 中间件 / reloader / 逐请求日志剥离出来做参照。
- 后端是 **SQLite 单文件**：写端点会被库级锁串行化，并发档位到某个点会掉吞吐 —— 这是库的特性，
  不是业务代码的问题；换 PG 必须重测。
- 客户端也是 Python（GIL + 线程池）：高并发档位的 QPS 上限里混有客户端自身开销，故给的是"下界观测值"。
- 单机、同机同库同 Config；跨机、跨库、真实网络 RTT 都不在本文覆盖范围。
"""
from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import platform
import statistics
import sys
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor

EMAIL = "core-accept-1@sim.local"
DEFAULT_ASK_QUERY = "介绍一下 THOMAS 架构的底座"  # 须命中 rag 意图；模板意图不烧 token
PWD = "Core-Accept-2026!"
CONSENT_SCOPES = ["ask_rag"]


# --------------------------------------------------------------------------- HTTP


class Session:
    """单线程复用一条 keep-alive 连接；异常时重建一次。"""

    def __init__(self, base):
        u = urllib.parse.urlsplit(base)
        self.scheme = u.scheme or "http"
        self.host = u.hostname or "127.0.0.1"
        self.port = u.port or (443 if self.scheme == "https" else 80)
        self.prefix = (u.path or "").rstrip("/")
        self._conn = None
        self._cls = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def call(self, path, method="GET", payload=None, token=None, timeout=120):
        """返回 (status, body_dict, elapsed_seconds)。"""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json; charset=utf-8", "Connection": "keep-alive"}
        if token:
            headers["Authorization"] = "Bearer " + token
        t0 = time.perf_counter()
        err = None
        for attempt in (0, 1):  # 长连接可能被服务端关掉：重连重试一次（不计入统计的假失败）
            try:
                if self._conn is None:
                    self._conn = self._cls(self.host, self.port, timeout=timeout)
                self._conn.request(method, self.prefix + path, body=body, headers=headers)
                resp = self._conn.getresponse()
                raw = resp.read()
                dt = time.perf_counter() - t0
                if resp.will_close:
                    self.close()
                try:
                    data = json.loads(raw.decode("utf-8", "replace"))
                except Exception:
                    data = {"_raw": raw[:200].decode("utf-8", "replace")}
                return resp.status, data, dt
            except Exception as exc:
                err = exc
                self.close()
                if attempt == 0:
                    continue
        return 0, {"_error": "%s: %s" % (type(exc).__name__, exc)}, time.perf_counter() - t0


_TLS = threading.local()


def sess(base):
    s = getattr(_TLS, "s", None)
    if s is None or s.base != base:
        s = Session(base)
        s.base = base
        _TLS.s = s
    return s


# --------------------------------------------------------------------------- 统计


def pct(values, p):
    """线性插值分位（与 numpy 默认口径一致，避免取整口径之争）。"""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def ms(x):
    return None if x is None else round(x * 1000.0, 1)


def summarize(lat, errs, statuses, err_samples):
    return {
        "n": len(lat),
        "errors": errs,
        "p50_ms": ms(pct(lat, 50)),
        "p95_ms": ms(pct(lat, 95)),
        "p99_ms": ms(pct(lat, 99)),
        "min_ms": ms(min(lat)) if lat else None,
        "max_ms": ms(max(lat)) if lat else None,
        "mean_ms": ms(statistics.fmean(lat)) if lat else None,
        "status": statuses,
        "error_samples": err_samples[:3],
    }


# --------------------------------------------------------------------------- 采集


def sequential(name, fn, rounds, warmup=5):
    """顺序打 rounds 次（warmup 不计入），返回统计。"""
    for _ in range(warmup):
        fn(0)
    lat, errs, statuses, samples = [], 0, {}, []
    for i in range(rounds):
        st, body, dt = fn(i)
        statuses[st] = statuses.get(st, 0) + 1
        if st != 200:
            errs += 1
            if len(samples) < 3:
                samples.append({"status": st, "body": json.dumps(body, ensure_ascii=False)[:160]})
            continue
        lat.append(dt)
    out = summarize(lat, errs, statuses, samples)
    out["endpoint"] = name
    return out


def sweep(name, fn, level, total):
    """固定并发 level、**总共**打 total 次，返回吞吐与延迟分位。"""
    lat, errs, statuses, samples = [], 0, {}, []
    lock = threading.Lock()

    def worker(start):
        nonlocal errs
        loc_lat, loc_err, loc_st, loc_smp = [], 0, {}, []
        for i in range(start, total, level):
            st, body, dt = fn(i)
            loc_st[st] = loc_st.get(st, 0) + 1
            if st != 200:
                loc_err += 1
                if len(loc_smp) < 2:
                    loc_smp.append({"status": st, "body": json.dumps(body, ensure_ascii=False)[:160]})
            else:
                loc_lat.append(dt)
        with lock:
            lat.extend(loc_lat)
            errs += loc_err
            for k, v in loc_st.items():
                statuses[k] = statuses.get(k, 0) + v
            samples.extend(loc_smp)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=level) as pool:
        list(pool.map(worker, range(level)))
    wall = time.perf_counter() - t0

    out = summarize(lat, errs, statuses, samples)
    out.update({
        "endpoint": name,
        "level": level,
        "requests": total,
        "wall_s": round(wall, 3),
        "qps": round(total / wall, 1) if wall > 0 else None,
    })
    return out


# --------------------------------------------------------------------------- 主流程


def main():
    ap = argparse.ArgumentParser(description="NFR 基线采集（延迟分位 / 并发档位 / ask token 成本）")
    ap.add_argument("--url", action="append", required=True,
                    metavar="NAME=URL", help="被测目标，可重复，如 core-fast=http://127.0.0.1:5301")
    ap.add_argument("--health-rounds", type=int, default=120)
    ap.add_argument("--auth-rounds", type=int, default=60)
    ap.add_argument("--consent-rounds", type=int, default=40)
    ap.add_argument("--ask-rounds", type=int, default=0, help="0 = 不测 ask（不花 token）")
    ap.add_argument("--ask-target", default="", help="ask 打哪个目标（默认取第一个）")
    ap.add_argument("--ask-query", default=DEFAULT_ASK_QUERY, help="ask 用的 query（默认命中 rag 的那句）")
    ap.add_argument("--levels", default="1,2,4,8,16,32")
    ap.add_argument("--per-level", type=int, default=200, help="每档总请求数（不是每线程）")
    ap.add_argument("--sweep-path", default="health", help="逗号分隔：health / profile / consent")
    ap.add_argument("--price-in", type=float, default=None, help="输入单价（元/百万 token）")
    ap.add_argument("--price-out", type=float, default=None, help="输出单价（元/百万 token）")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    targets = []
    for spec in args.url:
        if "=" not in spec:
            sys.exit("--url 需要 NAME=URL 形式：%s" % spec)
        n, u = spec.split("=", 1)
        targets.append((n, u.rstrip("/")))

    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    paths = [x.strip() for x in args.sweep_path.split(",") if x.strip()]
    result = {
        "env": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "cwd": os.getcwd(),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "params": {
            "health_rounds": args.health_rounds,
            "auth_rounds": args.auth_rounds,
            "consent_rounds": args.consent_rounds,
            "ask_rounds": args.ask_rounds,
            "levels": levels,
            "per_level": args.per_level,
            "sweep_path": paths,
        },
        "targets": {},
    }

    for name, base in targets:
        print("\n### %s  %s" % (name, base))
        st, body, dt = sess(base).call("/health", timeout=15)
        svc = (body or {}).get("service")
        commit = (body or {}).get("git_commit")
        print("health: status=%s service=%s commit=%s %.1fms" % (st, svc, commit, dt * 1000))

        st, body, dt = sess(base).call("/v1/auth/login", "POST", {"email": EMAIL, "password": PWD}, timeout=60)
        token = (body or {}).get("access_token", "")
        uid = ((body or {}).get("user") or {}).get("id", "")
        print("login : status=%s uid=%s %.1fms" % (st, uid, dt * 1000))
        if st != 200 or not token:
            print("！！login 失败，跳过该目标后续用例：%s" % json.dumps(body, ensure_ascii=False)[:200])
            result["targets"][name] = {"base": base, "health": {"service": svc, "commit": commit},
                                       "login": {"status": st, "body": body}}
            continue

        # 先把 ask_rag 授权拿到（幂等），后续 ask 才不会 403 consent_required
        st_c, body_c, _ = sess(base).call("/v1/compliance/consent/grant", "POST",
                                          {"scopes": CONSENT_SCOPES}, token=token, timeout=30)
        print("consent: status=%s %s" % (st_c, json.dumps(body_c, ensure_ascii=False)[:80]))

        def f_health(_i, _b=base):
            return sess(_b).call("/health", timeout=30)

        def f_profile(_i, _b=base, _t=token):
            return sess(_b).call("/v1/auth/profile", token=_t, timeout=60)

        def f_consent(_i, _b=base, _t=token):
            return sess(_b).call("/v1/compliance/consent/grant", "POST",
                                 {"scopes": CONSENT_SCOPES}, token=_t, timeout=60)

        def f_ask(_i, _b=base, _t=token):
            q = "%s（探针 %s）" % (args.ask_query, uuid.uuid4().hex[:8])
            return sess(_b).call("/v1/ask", "POST", {"query": q, "mode": "rag"}, token=_t, timeout=300)

        fns = {"health": f_health, "profile": f_profile, "consent": f_consent}
        seq = {k: sequential(k, fns[k], r) for k, r in (
            ("health", args.health_rounds), ("profile", args.auth_rounds), ("consent", args.consent_rounds))}
        sweeps = [sweep(pth, fns[pth], lv, args.per_level) for pth in paths for lv in levels]

        entry = {
            "base": base,
            "health": {"service": svc, "commit": commit},
            "login": {"status": st, "uid": uid, "ms": ms(dt)},
            "consent_bootstrap": {"status": st_c, "body": body_c},
            "sequential": seq,
            "sweeps": sweeps,
        }

        if args.ask_rounds and (not args.ask_target or args.ask_target == name):
            rounds, tokens, lat = [], [], []
            for i in range(args.ask_rounds):
                st2, body2, dt2 = f_ask(i)
                tk = (body2 or {}).get("tokens_used") or 0
                rounds.append({"i": i, "status": st2, "tokens": tk, "ms": ms(dt2),
                               "intent": (body2 or {}).get("intent"),
                               "answer_len": len((body2 or {}).get("answer") or "")})
                if st2 == 200 and tk:
                    tokens.append(tk)
                    lat.append(dt2)
            cost = None
            if tokens and args.price_in is not None and args.price_out is not None:
                tot = sum(tokens)
                cost = {
                    "total_tokens": tot,
                    "upper_bound_cny_all_input": round(tot * args.price_in / 1e6, 4),
                    "ref_cny_7in_3out": round(tot * (0.7 * args.price_in + 0.3 * args.price_out) / 1e6, 4),
                }
            entry["ask"] = {
                "rounds": rounds,
                "ok": len(tokens),
                "tokens_mean": round(statistics.fmean(tokens), 1) if tokens else None,
                "tokens_min": min(tokens) if tokens else None,
                "tokens_max": max(tokens) if tokens else None,
                "tokens_total": sum(tokens) if tokens else 0,
                "ms_p50": ms(pct(lat, 50)),
                "ms_p95": ms(pct(lat, 95)),
                "cost": cost,
            }

        result["targets"][name] = entry

    # ---------------------------------------------------------------- 输出

    print("\n\n## 顺序延迟（ms）\n")
    print("| 目标 | 端点 | n | p50 | p95 | p99 | min | max | 错误 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, e in result["targets"].items():
        for ep, s in (e.get("sequential") or {}).items():
            print("| %s | %s | %d | %s | %s | %s | %s | %s | %d |" % (
                name, ep, s["n"], s["p50_ms"], s["p95_ms"], s["p99_ms"], s["min_ms"], s["max_ms"], s["errors"]))
            if s["error_samples"]:
                print("|  | ↳ 错误样本 |  |  |  |  |  |  | %s |" % s["error_samples"][0]["body"][:90])

    print("\n## 并发档位（每档 %d 次）\n" % args.per_level)
    print("| 目标 | 端点 | 并发 | 请求 | QPS | p50 | p95 | p99 | 错误 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, e in result["targets"].items():
        for s in (e.get("sweeps") or []):
            print("| %s | %s | %d | %d | %s | %s | %s | %s | %d |" % (
                name, s["endpoint"], s["level"], s["requests"], s["qps"], s["p50_ms"], s["p95_ms"], s["p99_ms"], s["errors"]))

    asks = [(n, e["ask"]) for n, e in result["targets"].items() if e.get("ask")]
    if asks:
        print("\n## ask 端到端（token 成本）\n")
        print("| 目标 | 成功/总 | tokens 均值 | 最小 | 最大 | 合计 | p50 | p95 |")
        print("|---|---|---|---|---|---|---|---|")
        for n, a in asks:
            print("| %s | %d/%d | %s | %s | %s | %d | %s | %s |" % (
                n, a["ok"], len(a["rounds"]), a["tokens_mean"], a["tokens_min"], a["tokens_max"],
                a["tokens_total"], a["ms_p50"], a["ms_p95"]))
            if a["cost"]:
                print("|  | 成本 | %s |  |  |  |  |  |" % json.dumps(a["cost"], ensure_ascii=False))

    if args.out:
        d = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(d, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        print("\nJSON: %s" % args.out)


if __name__ == "__main__":
    main()
