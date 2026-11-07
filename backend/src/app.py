"""
Flask application factory.
Registers all blueprints, middleware, and error handlers.
"""
import os
from functools import lru_cache

from flask import Flask, abort, jsonify, render_template, send_from_directory
from flask_cors import CORS

from src.config import Config, _refresh_config
from src.thomas_core.runtime import git_commit

_HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

# Product-line tabs for the landing page. The last tuple element lists the
# /v1/<group> path segment(s) (as collected by _collect_endpoint_groups) that
# belong to that product line.
_PRODUCT_LINES = (
    ("planetx", "PlanetX", ("game", "narrative")),
    ("tspace", "T-space", ("enterprise",)),
    ("bolent", "Bolent", (
        "jobs", "job-posts", "resume", "application", "match-reports",
        "reports", "credit", "compliance", "trust", "timeline", "social",
    )),
    ("harmonyos", "HarmonyOS 元服务", ("payment/huawei", "push/huawei", "card")),
    ("shared", "通用 · 共享", ("auth", "ask", "quota", "payment", "referral", "analytics", "poetry")),
    ("system", "系统 · 运维", ("_sys", "admin", "endpoints")),
)


def _collect_endpoint_groups(app):
    """Enumerate registered routes from Flask's url_map, grouped by /v1/<group>/.

    Purely dynamic — adding/removing a blueprint is reflected here automatically,
    so the landing page and /v1/endpoints never need manual endpoint lists.
    Nested namespaces (/v1/payment/huawei/*, /v1/push/huawei/*) get a two-level key.
    """
    raw = {}
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        methods = sorted((rule.methods or set()) & set(_HTTP_METHODS))
        if not methods or rule.rule.startswith("/static"):
            continue
        parts = [p for p in rule.rule.split("/") if p]
        if len(parts) >= 2 and parts[0] == "v1":
            # Two-level key only for vendor sub-namespaces: /v1/payment/huawei/*,
            # /v1/push/huawei/* — plain /v1/payment/plans stays in the payment group.
            if len(parts) >= 3 and parts[2] == "huawei":
                key = f"{parts[1]}/{parts[2]}"
            else:
                key = parts[1]
        else:
            key = "_sys"
        raw.setdefault(key, []).append({"methods": methods, "rule": rule.rule})

    ordered = []
    sys_routes = raw.pop("_sys", [])
    if sys_routes:
        ordered.append({"key": "_sys", "label": "系统 · 根 / 健康 / 运维", "routes": sys_routes})
    for key in sorted(raw):
        ordered.append({"key": key, "label": f"/v1/{key}/", "routes": raw[key]})
    return ordered


def _collect_product_lines(app):
    """Map collected endpoint groups onto product-line tabs (order preserved).

    Groups not matched by any product line automatically land in the
    "通用 · 共享" tab so new blueprints never silently disappear.
    """
    groups = _collect_endpoint_groups(app)
    by_key = {g["key"]: g for g in groups}
    lines = []
    for line_key, label, group_keys in _PRODUCT_LINES:
        line_groups = [by_key[k] for k in group_keys if k in by_key]
        if line_groups:
            lines.append({
                "key": line_key,
                "label": label,
                "total": sum(len(g["routes"]) for g in line_groups),
                "groups": line_groups,
            })
    mapped = {k for _, _, group_keys in _PRODUCT_LINES for k in group_keys}
    unmatched = [g for g in groups if g["key"] not in mapped]
    if unmatched:
        shared = next((l for l in lines if l["key"] == "shared"), None)
        if shared:
            shared["groups"].extend(unmatched)
            shared["total"] += sum(len(g["routes"]) for g in unmatched)
        else:
            lines.append({
                "key": "shared", "label": "通用 · 共享",
                "total": sum(len(g["routes"]) for g in unmatched),
                "groups": unmatched,
            })
    return lines


def _qcc_gateway_status():
    """Resolve the QCC (企查查) MCP gateway the backend consumes.

    The gateway is an external nginx/ServBay reverse proxy (:8998) that fronts
    agent.qcc.com — it is NOT a Flask route, so it never shows up in the
    url_map-based endpoint inventory; it's surfaced here as a dependency.
    """
    from src.credit.qcc_client import _mcp_base_url, get_qcc_base_urls

    base = _mcp_base_url()
    try:
        import requests as _req

        resp = _req.get(f"{base.rstrip('/')}/health", timeout=2)
        status = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
    except Exception:
        status = "unreachable"
    return {
        "base": base,
        "status": status,
        "services": get_qcc_base_urls(),
    }


def _probe_base(base: str, auth_token: str = "") -> str:
    """Lightweight liveness probe against an OpenAI-compatible / Ollama endpoint.

    Tries the known health-ish GET paths; any HTTP response means the host is
    reachable (a 4xx may just be auth/route variance), only a total connect
    failure is reported as unreachable.
    """
    import requests as _req

    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
    seen: set[int] = set()
    for path in ("/models", "/api/tags", "/v1/models"):
        try:
            resp = _req.get(f"{base.rstrip('/')}{path}", headers=headers, timeout=2)
            seen.add(resp.status_code)
            if resp.status_code == 200:
                return "ok"
        except Exception:
            continue
    if seen:
        return "http_" + "/".join(str(s) for s in sorted(seen))
    return "unreachable"


def _collect_dependencies(app):
    """External services the backend consumes: QCC gateway + LLM providers.

    These are NOT Flask routes, so they never appear in the url_map-based
    endpoint inventory below; they are surfaced here as dependencies.
    """
    import requests as _req  # noqa: F401  (kept for parity with qcc probe)

    deps = {"qcc": _qcc_gateway_status(), "llm": []}
    order = [
        p.strip().lower()
        for p in (
            app.config.get("LLM_PROVIDER_ORDER")
            or os.getenv("LLM_PROVIDER_ORDER")
            or "deepseek"
        ).split(",")
        if p.strip()
    ]
    for p in order:
        if p == "deepseek":
            key = (app.config.get("DEEPSEEK_API_KEY") or "").strip()
            base = app.config.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
            model = app.config.get("DEEPSEEK_MODEL") or "deepseek-chat"
        elif p == "openai":
            key = (app.config.get("OPENAI_API_KEY") or "").strip()
            base = app.config.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
            model = app.config.get("OPENAI_MODEL") or "gpt-3.5-turbo"
        elif p == "ollama":
            key = "local"  # always considered configured (no auth)
            base = app.config.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
            model = app.config.get("OLLAMA_MODEL") or "qwen2.5-coder:1.5b"
        else:
            deps["llm"].append({"name": p, "base": "", "model": "", "status": "unknown", "cls": "bad"})
            continue
        if key and key.lower() not in ("skip", "your-deepseek-api-key", "your-openai-api-key"):
            status = _probe_base(base, key if p != "ollama" else "")
        else:
            status = "not_configured"
        cls = {
            "ok": "ok",
            "not_configured": "muted",
            "unreachable": "bad",
        }.get(status, "warn")  # http_* → warn
        deps["llm"].append({"name": p, "base": base, "model": model, "status": status, "cls": cls})
    return deps


def _collect_open_items(app):
    """Known gaps / tasks needing attention — dynamic probes + team list."""
    from src.open_items import load_open_items

    return load_open_items(app)


@lru_cache(maxsize=1)
def _git_commit() -> str:
    """兼容壳：实现已收进核（刀 5a，`src/thomas_core/runtime.git_commit`）。

    保留本名字是因为宿主内多处（`/health`、`_dual_track_health_ids`）与既有测试
    都在叫它；产品→核 的 import 方向是允许的。缓存由核那侧按 env 值记忆，
    这里不再叠一层 lru_cache（叠了会让 monkeypatch GIT_COMMIT 失效）。
    """
    return git_commit()


def _dual_track_health_ids() -> dict:
    """Lock 4：双轨探活「认对树」。

    探活规则（禁止互相冒充）：
    - looma / 天翼 tip → 认 `looma_sha`（== `git_commit`）；`stack_sha`/`vultr_tag` 必须 null
    - vultr / SG tip → 认 `stack_sha` + `vultr_tag`；`looma_sha` 仅是 join PIN，不是 tip
    - 禁止拿 CN.`looma_sha` 与 SG.`looma_sha` 比「谁落后」
    """
    commit = _git_commit()
    region = (os.getenv("DEPLOY_REGION") or "").strip().upper()
    env_looma = (
        os.getenv("LOOMA_SHA", "").strip()
        or os.getenv("LOOMA_JOIN_SHA", "").strip()
    )
    vultr_tag = (
        os.getenv("VULTR_TAG", "").strip()
        or os.getenv("STACK_TAG", "").strip()
        or None
    )
    env_stack = os.getenv("STACK_SHA", "").strip() or None
    # Track from DEPLOY_REGION / VULTR_TAG only — stray STACK_SHA on CN must not flip.
    is_vultr = region in ("SG", "US", "FRA") or bool(vultr_tag)

    if is_vultr:
        # join PIN only — never fall back to stack tip (would impersonate looma tip)
        looma_sha = env_looma or None
        stack_sha = env_stack or (commit if commit != "unknown" else None)
        return {
            "deploy_track": "vultr",
            "looma_sha": looma_sha,
            "looma_sha_kind": "join_pin" if looma_sha else None,
            "vultr_tag": vultr_tag,
            "stack_sha": stack_sha,
        }

    # CN / looma：tip = looma_sha；拒绝带回 stack 标记冒充海外轨
    tip = env_looma or (commit if commit != "unknown" else None)
    return {
        "deploy_track": "looma",
        "looma_sha": tip,
        "looma_sha_kind": "deploy_tip" if tip else None,
        "vultr_tag": None,
        "stack_sha": None,
    }


def create_app(env="development"):
    app = Flask(__name__)
    _refresh_config()  # re-read env vars so per-test overrides are picked up
    app.config.from_object(Config)

    # CORS
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)

    # --- Register blueprints ---
    from src.thomas_core.routes.auth_routes import auth_bp
    from src.api.routes.game_routes import game_bp
    from src.api.routes.enterprise_routes import enterprise_bp
    from src.api.routes.job_post_routes import job_post_bp
    from src.thomas_core.routes.ask_routes import ask_bp
    from src.api.routes.jobs_routes import jobs_bp
    from src.api.routes.application_routes import application_bp
    from src.api.routes.resume_routes import resume_bp
    from src.api.routes.reports_routes import reports_bp
    from src.api.routes.match_report_routes import match_report_bp
    from src.api.routes.referral_routes import referral_bp
    from src.api.routes.credit_routes import credit_bp
    from src.api.routes.quota_routes import quota_bp
    from src.api.routes.payment_routes import payment_bp
    from src.api.routes.poetry_routes import poetry_bp
    from src.api.routes.narrative_routes import narrative_bp
    from src.thomas_core.routes.compliance_routes import compliance_bp
    from src.api.routes.analytics_routes import analytics_bp
    from src.api.routes.admin_routes import admin_bp
    from src.api.routes.social_routes import social_bp  # 六度分隔社交图谱
    from src.api.routes.trust_routes import trust_bp    # Trust Agent 信任证明
    from src.api.routes.timeline_routes import timeline_bp  # Career timeline
    from src.api.routes.huawei_iap_routes import huawei_iap_bp  # HarmonyOS IAP
    from src.api.routes.huawei_push_routes import huawei_push_bp  # HarmonyOS Push
    from src.api.routes.card_routes import card_bp  # HarmonyOS Card API
    from src.api.routes.driver_content_routes import (  # 橱窗/书店多租户 API + 通道 B 内容信号
        driver_content_bp, signal_content_bp,
    )

    # Phase 1：THOMAS_CORE_MODE=http 时，核面（auth/ask/compliance）不装进宿主进程，
    # 改由 core_proxy 蓝图转发到核进程（:5300）；inprocess 为默认，行为与刀 4 前一致。
    from src.thomas_core import client as core_client

    if core_client.http_mode():
        from src.api.routes.core_proxy_routes import core_proxy_bp

        app.register_blueprint(core_proxy_bp)
        app.logger.info("[host] core mode=http → proxy to %s", core_client.base_url())
    else:
        app.register_blueprint(auth_bp, url_prefix="/v1/auth")
    app.register_blueprint(game_bp, url_prefix="/v1/game")
    app.register_blueprint(enterprise_bp, url_prefix="/v1/enterprise")
    app.register_blueprint(job_post_bp, url_prefix="/v1")
    if not core_client.http_mode():
        app.register_blueprint(ask_bp, url_prefix="/v1")
    app.register_blueprint(jobs_bp, url_prefix="/v1/jobs")
    app.register_blueprint(application_bp, url_prefix="/v1")
    app.register_blueprint(resume_bp, url_prefix="/v1/resume")
    app.register_blueprint(reports_bp, url_prefix="/v1/reports")
    app.register_blueprint(match_report_bp, url_prefix="/v1/match-reports")
    app.register_blueprint(referral_bp, url_prefix="/v1/referral")
    app.register_blueprint(credit_bp, url_prefix="/v1/credit")
    if not core_client.http_mode():
        app.register_blueprint(compliance_bp, url_prefix="/v1/compliance")
    app.register_blueprint(quota_bp, url_prefix="/v1")
    app.register_blueprint(payment_bp, url_prefix="/v1")
    app.register_blueprint(poetry_bp, url_prefix="/v1/poetry")
    app.register_blueprint(narrative_bp, url_prefix="/v1/narrative")
    app.register_blueprint(analytics_bp, url_prefix="/v1")
    app.register_blueprint(admin_bp, url_prefix="/v1")  # /v1/admin/*
    app.register_blueprint(social_bp, url_prefix="/v1/social")  # 六度分隔社交图谱
    app.register_blueprint(trust_bp, url_prefix="/v1/trust")    # Trust Agent 信任证明
    app.register_blueprint(timeline_bp, url_prefix="/v1/timeline")  # Career timeline
    app.register_blueprint(huawei_iap_bp, url_prefix="/v1/payment/huawei")  # HarmonyOS IAP
    app.register_blueprint(huawei_push_bp, url_prefix="/v1/push/huawei")  # HarmonyOS Push
    app.register_blueprint(card_bp, url_prefix="/v1")  # HarmonyOS Cards (/v1/card/*)
    app.register_blueprint(driver_content_bp, url_prefix="/v1/driver")  # 多租户内容
    app.register_blueprint(signal_content_bp, url_prefix="/v1")  # 通道 B：/v1/signals/content

    # --- Health check ---
    @app.route("/health", methods=["GET"])
    def health():
        import os

        llm_order_raw = (
            app.config.get("LLM_PROVIDER_ORDER")
            or os.getenv("LLM_PROVIDER_ORDER")
            or "deepseek"
        )
        llm_order = [
            p.strip().lower()
            for p in str(llm_order_raw).split(",")
            if p.strip()
        ] or ["deepseek"]
        primary_llm = llm_order[0]

        has_deepseek = bool(
            (app.config.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "").strip()
        )
        has_openai = bool(
            (app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
        )
        # Ollama needs no cloud key; treat as configured when present in the fallback order
        has_ollama = "ollama" in llm_order
        has_qcc = bool(
            (app.config.get("QCC_AUTH_TOKEN") or os.getenv("QCC_AUTH_TOKEN") or "").strip()
        )
        qcc_enabled = str(
            app.config.get("QCC_ENABLED", os.getenv("QCC_ENABLED", "true"))
        ).lower() in ("1", "true", "yes", "on")

        llm_ready = (
            (primary_llm == "deepseek" and has_deepseek)
            or (primary_llm == "openai" and has_openai)
            or primary_llm == "ollama"
            or has_deepseek
            or has_openai
        )
        track_ids = _dual_track_health_ids()
        return jsonify(
            status="ok" if llm_ready else "degraded",
            service="looma-backend",
            version="v1",
            git_commit=_git_commit(),
            deploy_track=track_ids["deploy_track"],
            looma_sha=track_ids["looma_sha"],
            looma_sha_kind=track_ids["looma_sha_kind"],
            vultr_tag=track_ids["vultr_tag"],
            stack_sha=track_ids["stack_sha"],
            llm_provider=primary_llm,
            llm_provider_order=llm_order,
            llm_configured=llm_ready,
            # Booleans only — never expose key material
            providers_configured={
                "openai": has_openai,
                "deepseek": has_deepseek,
                "ollama": has_ollama,
            },
            qcc_configured=has_qcc and qcc_enabled,
        )

    # --- SPA mode: serve PlanetX frontend as a single-app deployment ---
    # Set PLANETX_DIST_DIR env var to the PlanetX build output directory.
    # When enabled, Flask serves the SPA at / and all non-API routes,
    # replacing the JSON API info root endpoint.
    _planetx_dist = os.getenv("PLANETX_DIST_DIR", "")
    _spa_enabled = bool(_planetx_dist and os.path.isdir(_planetx_dist))

    if _spa_enabled:
        @app.route("/", methods=["GET"])
        def serve_spa_root():
            return send_from_directory(_planetx_dist, "index.html")

        @app.route("/<path:spa_path>")
        def serve_spa(spa_path):
            # /v1/* is handled by blueprints — if we reach here it's a 404
            if spa_path.startswith("v1/"):
                abort(404)
            file_path = os.path.join(_planetx_dist, spa_path)
            if os.path.isfile(file_path):
                return send_from_directory(_planetx_dist, spa_path)
            # SPA fallback: all client-side routes → index.html
            return send_from_directory(_planetx_dist, "index.html")
    else:
        # --- Root: API-only landing page (team-internal) ---
        # In this mode the backend exposes only /v1/* APIs; the product UIs
        # (PlanetX / T-space / portal) run as separate apps and call this API.
        @app.route("/", methods=["GET"])
        def api_landing():
            from datetime import datetime

            lines = _collect_product_lines(app)
            route_total = sum(l["total"] for l in lines)
            return render_template(
                "root.html",
                service="looma-backend",
                version="v1",
                env=os.getenv("FLASK_ENV", "development"),
                llm_provider=(
                    app.config.get("LLM_PROVIDER_ORDER")
                    or os.getenv("LLM_PROVIDER_ORDER")
                    or "deepseek"
                ).split(",")[0].strip(),
                route_total=route_total,
                product_lines=lines,
                deps=_collect_dependencies(app),
                open_items=_collect_open_items(app),
                generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

        @app.route("/v1/endpoints", methods=["GET"])
        def api_endpoints():
            """Machine-readable endpoint inventory — dynamically generated."""
            return jsonify(
                service="looma-backend",
                status="ok",
                version="v1",
                generated_from="app.url_map (dynamic, no manual maintenance)",
                endpoints={
                    g["key"]: [
                        f"{' '.join(r['methods'])} {r['rule']}" for r in g["routes"]
                    ]
                    for g in _collect_endpoint_groups(app)
                },
            )

    # --- Error handlers ---
    @app.errorhandler(404)
    def not_found(e):
        from flask import request as _req
        path = _req.path
        if path.startswith("/v1/"):
            msg = f"Endpoint {path} not found. See GET /v1/endpoints for the full list."
        else:
            msg = f"Endpoint {path} not found."
        return jsonify(error="not_found", message=msg), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify(error="server_error", message=str(e)), 500

    # --- Initialize database on first request ---
    from src.db import schema_loader
    from src.db.manager import DatabaseManager

    @app.before_request
    def init_db():
        if not getattr(app, "_db_initialized", False):
            db_path = app.config["DATABASE_PATH"]
            split = schema_loader.split_enabled()
            if split and db_path != ":memory:":
                # product 侧外键/视图依赖 core 的 users → core 必须先建。
                # 空库（冷启动）是例外：此刻没有任何一方"拥有"表，宿主用同一份 loader
                # 依次建 core → product，产出与 legacy 完全相同的 58 表 + 3 视图；
                # 只有「库非空但缺 core」才 fail-fast（那通常意味着指错了库文件）。
                if schema_loader.is_empty(db_path):
                    boot = schema_loader.ensure_scope(db_path, "core")
                    app.logger.info("[host] cold start → core scope bootstrapped: %s", boot)
                elif not schema_loader.core_ready(db_path):
                    raise RuntimeError(
                        "core schema missing: 库非空但缺 core 的 users 等 7 表。\n"
                        "请先启动核进程（backend/run_core.py，:5300）完成 core schema 初始化，"
                        "或临时设 THOMAS_SCHEMA_SPLIT=0 走 legacy 全量建表。"
                    )
                info = schema_loader.ensure_scope(db_path, "product")
                app.logger.info("[host] schema scope=product ensured: %s", info)
            db = DatabaseManager(db_path)
            if not split or db_path == ":memory:":
                db.init_schema()

            # Auto-seed beta users in dev mode
            if app.config.get("FLASK_ENV") == "development":
                try:
                    seeded = db.seed_beta_users()
                    if seeded:
                        app.logger.info(f"[dev] Seeded {len(seeded)} beta users: {seeded}")
                except Exception as e:
                    app.logger.warning(f"[dev] seed_beta_users skipped: {e}")

            app._db = db
            app._db_initialized = True

    # --- R1 键位强制（Phase 1）：in-process 模式下宿主同样要校验 X-User-Id ---
    # http 模式由核进程校验（代理只透传该头），故此处不重复注册。
    if not core_client.http_mode():
        from src.thomas_core.keys import register_user_id_key_guard

        register_user_id_key_guard(app)

    # --- 核钩子注册（刀 5e/5f）：时间线埋点 / 匹配报告 / 意图大脑由宿主注入 ---
    # 核不再硬 import 产品模块；这里把宿主实现挂上去。注册失败不阻断启动 ——
    # 核的钩子本身有惰性缺省（宿主不在时不报错），所以 try/except 只是保险。
    from src.thomas_core import brain as _core_brain
    from src.thomas_core import hooks as _core_hooks

    try:
        from src.reports.match_report_manager import MatchReportManager as _MatchReportManager
        from src.timeline.events import record_interaction_log as _record_interaction_log

        _core_hooks.register_timeline_logger(_record_interaction_log)
        _core_hooks.register_report_manager_factory(_MatchReportManager)

        from src.agents.central_brain import dispatch as _brain_dispatch
        from src.agents.central_brain import parse_intent as _brain_parse_intent

        _core_brain.register_brain(_brain_parse_intent, _brain_dispatch)
    except Exception:  # pragma: no cover - 裁剪部署时的保险
        app.logger.warning("[core-hooks] 宿主实现注册失败，回落核的惰性缺省", exc_info=True)

    return app
