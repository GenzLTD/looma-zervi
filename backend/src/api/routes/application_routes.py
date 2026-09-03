"""
Job application routes — DemoPeter thin-ingest → HR-visible apply records.

Endpoints:
  POST   /v1/application              - Seeker applies resume_id to job_id
  GET    /v1/application              - Seeker lists own applications
  GET    /v1/application/<id>         - Get one (seeker owner or job HR)
  GET    /v1/application/<id>/report  - Lazy match report (contract P0)
  DELETE /v1/application/<id>         - Withdraw (HR no longer sees resume body)
  GET    /v1/jobs/<job_id>/applications - HR lists active applications for a job
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from flask import Blueprint, current_app, g, jsonify, request

from src.api.auth.decorators import require_auth
from src.compliance.consent import require_consent

logger = logging.getLogger("looma.application")
application_bp = Blueprint("application", __name__)

_SHA_TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_SHA_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def _db():
    from src.db.manager import DatabaseManager

    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
    return DatabaseManager(db_path)


def _row_to_app(row) -> dict:
    d = dict(row)
    try:
        meta = json.loads(d.get("metadata") or "{}")
    except json.JSONDecodeError:
        meta = {}
    return {
        "id": d["id"],
        "seeker_user_id": d["seeker_user_id"],
        "resume_id": d["resume_id"],
        "job_id": d["job_id"],
        "enterprise_id": d.get("enterprise_id") or "",
        "status": d["status"],
        "metadata": meta if isinstance(meta, dict) else {},
        "created_at": d["created_at"],
        "updated_at": d["updated_at"],
        "withdrawn_at": d.get("withdrawn_at"),
    }


def _get_resume_owned(conn, resume_id: str, seeker_user_id: str):
    row = conn.execute(
        "SELECT id, title, metadata, status FROM documents WHERE id = ? AND doc_type = 'resume'",
        (resume_id,),
    ).fetchone()
    if not row:
        return None
    try:
        meta = json.loads(row["metadata"] or "{}")
    except json.JSONDecodeError:
        meta = {}
    if str(meta.get("user_id") or "") != str(seeker_user_id):
        return None
    return row, meta if isinstance(meta, dict) else {}


def _job_owner_user_id(conn, job_id: str) -> str | None:
    """Resolve owner for persisted job document or job_posts row."""
    # documents.metadata.job_id
    rows = conn.execute(
        """SELECT metadata FROM documents
           WHERE doc_type = 'job' AND status = 'processed'"""
    ).fetchall()
    for r in rows:
        try:
            meta = json.loads(r["metadata"] or "{}")
        except json.JSONDecodeError:
            continue
        jid = meta.get("job_id") or (meta.get("parsed") or {}).get("id")
        if str(jid) == str(job_id):
            return str(meta.get("user_id") or "") or None

    # job_posts.id
    jp = conn.execute(
        "SELECT user_id FROM job_posts WHERE id = ?", (job_id,)
    ).fetchone()
    if jp:
        return str(jp["user_id"])
    return None


def _job_exists(conn, job_id: str) -> bool:
    if _job_owner_user_id(conn, job_id) is not None:
        return True
    # Allow apply to known mock/demo ids even before seed (CN fixtures)
    from src.api.routes.jobs_routes import MOCK_JOBS

    return any(str(j["id"]) == str(job_id) for j in MOCK_JOBS)


def _can_view_as_hr(conn, viewer_user_id: str, job_id: str) -> bool:
    owner = _job_owner_user_id(conn, job_id)
    if owner and owner == str(viewer_user_id):
        return True
    user = conn.execute(
        "SELECT role FROM users WHERE id = ?", (viewer_user_id,)
    ).fetchone()
    if user and (user["role"] or "") in ("admin", "hr", "enterprise"):
        return True
    # Enterprise member linked to application.enterprise_id checked at call site
    return False


def _resume_payload_for_hr(meta: dict, *, include_body: bool) -> dict:
    """HR-visible resume summary; body only when application is active."""
    extracted = meta.get("extracted") if isinstance(meta.get("extracted"), dict) else {}
    out = {
        "filename": meta.get("filename") or "",
        "has_extracted": bool(extracted),
        "skills": (extracted or {}).get("skills") or [],
        "name": (extracted or {}).get("name"),
    }
    if include_body:
        md = meta.get("markdown") or ""
        out["markdown"] = md[:8000] if isinstance(md, str) else ""
        out["extracted"] = extracted
    else:
        out["markdown"] = None
        out["extracted"] = None
        out["redacted"] = True
    return out


@application_bp.route("/application", methods=["POST"])
@require_auth
@require_consent("application_submit")
def create_application():
    """Seeker: bind resume_id to job_id as a submitted application."""
    data = request.get_json() or {}
    resume_id = str(data.get("resume_id") or "").strip()
    job_id = str(data.get("job_id") or "").strip()
    enterprise_id = str(data.get("enterprise_id") or "").strip()
    if not resume_id or not job_id:
        return jsonify(error="bad_request", message="resume_id and job_id are required"), 400

    seeker = str(g.user_id)
    db = _db()
    now = _now_iso()

    with db.get_conn() as conn:
        owned = _get_resume_owned(conn, resume_id, seeker)
        if not owned:
            return jsonify(error="not_found", message="简历不存在或不属于当前用户"), 404
        _row, resume_meta = owned

        if not _job_exists(conn, job_id):
            return jsonify(error="not_found", message="职位不存在"), 404

        existing = conn.execute(
            """SELECT id, status FROM applications
               WHERE seeker_user_id = ? AND resume_id = ? AND job_id = ?
                 AND status = 'submitted'""",
            (seeker, resume_id, job_id),
        ).fetchone()
        if existing:
            return jsonify(
                application=_row_to_app(
                    conn.execute(
                        "SELECT * FROM applications WHERE id = ?", (existing["id"],)
                    ).fetchone()
                ),
                already_exists=True,
            ), 200

        app_id = str(uuid.uuid4())
        meta = {
            "source": data.get("source") or "api",
            "resume_title": _row["title"],
        }
        conn.execute(
            """INSERT INTO applications
               (id, seeker_user_id, resume_id, job_id, enterprise_id, status, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'submitted', ?, ?, ?)""",
            (
                app_id,
                seeker,
                resume_id,
                job_id,
                enterprise_id,
                json.dumps(meta, ensure_ascii=False),
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()

    logger.info(
        "application created id=%s seeker=%s resume=%s job=%s",
        app_id,
        seeker,
        resume_id,
        job_id,
    )
    return jsonify(application=_row_to_app(row), already_exists=False), 201


@application_bp.route("/application", methods=["GET"])
@require_auth
def list_my_applications():
    """Seeker: list own applications (including withdrawn)."""
    seeker = str(g.user_id)
    status = (request.args.get("status") or "").strip()
    db = _db()
    with db.get_conn() as conn:
        if status:
            rows = conn.execute(
                """SELECT * FROM applications
                   WHERE seeker_user_id = ? AND status = ?
                   ORDER BY created_at DESC LIMIT 100""",
                (seeker, status),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM applications
                   WHERE seeker_user_id = ?
                   ORDER BY created_at DESC LIMIT 100""",
                (seeker,),
            ).fetchall()
    apps = [_row_to_app(r) for r in rows]
    return jsonify(applications=apps, total=len(apps))


@application_bp.route("/application/<application_id>", methods=["GET"])
@require_auth
def get_application(application_id: str):
    db = _db()
    viewer = str(g.user_id)
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not row:
            return jsonify(error="not_found", message="投递记录不存在"), 404
        app = _row_to_app(row)
        is_seeker = app["seeker_user_id"] == viewer
        is_hr = _can_view_as_hr(conn, viewer, app["job_id"])
        if not is_seeker and not is_hr:
            return jsonify(error="forbidden", message="无权查看该投递"), 403

        payload = {"application": app}
        if is_hr:
            resume_row = conn.execute(
                "SELECT metadata FROM documents WHERE id = ? AND doc_type = 'resume'",
                (app["resume_id"],),
            ).fetchone()
            try:
                rmeta = json.loads((resume_row["metadata"] if resume_row else None) or "{}")
            except json.JSONDecodeError:
                rmeta = {}
            include_body = app["status"] == "submitted"
            payload["resume"] = _resume_payload_for_hr(rmeta, include_body=include_body)
        return jsonify(payload)


def _load_resume_text(conn, resume_id: str) -> tuple[str | None, dict]:
    row = conn.execute(
        "SELECT metadata, title FROM documents WHERE id = ? AND doc_type = 'resume'",
        (resume_id,),
    ).fetchone()
    if not row:
        return None, {}
    try:
        meta = json.loads(row["metadata"] or "{}")
    except json.JSONDecodeError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    text = (meta.get("markdown") or "").strip()
    if not text and isinstance(meta.get("extracted"), dict):
        text = json.dumps(meta["extracted"], ensure_ascii=False)
    return (text or None), meta


def _resolve_job(job_id: str) -> dict | None:
    from src.api.routes.jobs_routes import _fallback_jobs, _get_persisted_jobs

    for j in _get_persisted_jobs() or []:
        if str(j.get("id")) == str(job_id):
            return j
    for j in _fallback_jobs() or []:
        if str(j.get("id")) == str(job_id):
            return j
    return None


def _find_cached_application_report(conn, resume_id: str, job_id: str) -> dict | None:
    row = conn.execute(
        """SELECT id, metadata, summary, created_at FROM match_reports
           WHERE resume_id = ? AND status != 'deleted'
             AND json_extract(metadata, '$.job_id') = ?
             AND json_extract(metadata, '$.report_type') = 'application'
           ORDER BY created_at DESC LIMIT 1""",
        (str(resume_id), str(job_id)),
    ).fetchone()
    if not row:
        return None
    item = conn.execute(
        """SELECT * FROM match_report_items
           WHERE report_id = ? ORDER BY rank_order ASC LIMIT 1""",
        (row["id"],),
    ).fetchone()
    if not item:
        return None
    return {"report": dict(row), "item": dict(item)}


def _item_to_match_report_payload(item: dict, *, report_id: str, cached: bool, generated_at: str) -> dict:
    try:
        matched = json.loads(item.get("matched_skills") or "[]")
    except json.JSONDecodeError:
        matched = []
    try:
        missing = json.loads(item.get("missing_skills") or "[]")
    except json.JSONDecodeError:
        missing = []
    try:
        gaps_raw = json.loads(item.get("gap_analysis") or "[]")
    except json.JSONDecodeError:
        gaps_raw = []
    gaps = []
    for g_item in gaps_raw if isinstance(gaps_raw, list) else []:
        if not isinstance(g_item, dict):
            continue
        gaps.append({
            "skill": g_item.get("skill") or "",
            "importance": g_item.get("importance") or g_item.get("priority") or "preferred",
            "suggestion": g_item.get("suggestion") or "",
        })
    plan = (item.get("improvement_plan") or "").strip()
    suggestions = [s.strip() for s in plan.split("\n") if s.strip()] if plan else []
    if item.get("match_reason"):
        suggestions = [item["match_reason"]] + suggestions
    score = float(item.get("overall_score") or 0)
    # Contract uses 0-1; pipeline often uses 0-100
    if score > 1.0:
        score = round(score / 100.0, 4)
    return {
        "report_id": report_id,
        "cached": cached,
        "overall_score": score,
        "skill_match": {
            "matched": matched if isinstance(matched, list) else [],
            "missing": missing if isinstance(missing, list) else [],
            "partial": [],
        },
        "gaps": gaps,
        "suggestions": suggestions[:8],
        "generated_at": generated_at,
    }


def _heuristic_match(resume_text: str, job: dict) -> dict:
    """Offline fallback when LLM match pipeline is unavailable."""
    import re

    resume_l = resume_text.lower()
    desc = f"{job.get('title') or ''} {job.get('description') or ''}"
    tokens = set(re.findall(r"[a-zA-Z+]{2,}|\w{2,}", desc.lower()))
    stop = {"and", "the", "for", "with", "job", "职位", "要求", "经验"}
    tokens = {t for t in tokens if t not in stop and len(t) > 1}
    matched = sorted(t for t in tokens if t in resume_l)[:12]
    missing = sorted(t for t in tokens if t not in resume_l)[:8]
    overlap = len(matched) / max(len(tokens), 1)
    score = round(min(0.95, 0.35 + overlap * 0.6), 4)
    gaps = [
        {
            "skill": m,
            "importance": "preferred",
            "suggestion": f"可补充与「{m}」相关的项目或表述",
        }
        for m in missing[:5]
    ]
    return {
        "id": job.get("id"),
        "title": job.get("title") or "",
        "company": job.get("company") or "",
        "description": job.get("description") or "",
        "scores": {"overall": score * 100},
        "overall_score": score * 100,
        "matched_skills": matched,
        "missing_skills": missing,
        "gap_analysis": gaps,
        "improvement_plan": "\n".join(
            g["suggestion"] for g in gaps
        ) or "继续完善与目标岗位关键词对齐的经历描述",
        "reason": f"启发式匹配分 {score:.0%}（引擎降级）",
    }


@application_bp.route("/application/<application_id>/report", methods=["GET"])
@require_auth
def get_application_report(application_id: str):
    """Lazy match report for an application (see docs/CONTRACT_APPLICATION_REPORT.md)."""
    viewer = str(g.user_id)
    refresh = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    db = _db()

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not row:
            return jsonify(
                error="not_found",
                message=f"application {application_id} 不存在",
            ), 404
        app = _row_to_app(row)
        is_seeker = app["seeker_user_id"] == viewer
        is_hr = _can_view_as_hr(conn, viewer, app["job_id"])
        if not is_seeker and not is_hr:
            return jsonify(
                error="forbidden",
                message="你不是该投递的求职者或该职位的 HR",
            ), 403

        resume_id = app["resume_id"]
        job_id = app["job_id"]
        job = _resolve_job(job_id)
        job_title = (job or {}).get("title") or job_id

        if not refresh:
            cached = _find_cached_application_report(conn, resume_id, job_id)
            if cached:
                payload = _item_to_match_report_payload(
                    cached["item"],
                    report_id=cached["report"]["id"],
                    cached=True,
                    generated_at=cached["report"].get("created_at") or "",
                )
                return jsonify(
                    application_id=application_id,
                    resume_id=resume_id,
                    job_id=job_id,
                    job_title=job_title,
                    match_report=payload,
                )

        resume_text, _meta = _load_resume_text(conn, resume_id)
        resume_ready = bool(resume_text and len(resume_text.strip()) >= 20)
        job_ready = bool(job and ((job.get("description") or job.get("title") or "").strip()))

        if not resume_ready or not job_ready:
            return jsonify(
                error="unprocessable",
                message="resume/job 内容不足以计算匹配",
                detail={"resume_ready": resume_ready, "job_ready": job_ready},
            ), 422

    # Compute outside the read transaction
    match_item = None
    try:
        from src.pipeline.job_match_pipeline import run_job_match_pipeline

        matches, _total = run_job_match_pipeline(
            resume_text=resume_text,
            jobs=[job],
        )
        if matches:
            match_item = matches[0]
    except Exception as e:
        logger.warning("application report LLM match failed, heuristic fallback: %s", e)
        match_item = None

    if not match_item:
        try:
            match_item = _heuristic_match(resume_text, job)
        except Exception as e:
            logger.warning("application report heuristic failed: %s", e)
            return jsonify(
                error="unprocessable",
                message="匹配引擎不可用",
                detail={"reason": "engine_unavailable"},
            ), 422

    # Persist cache (optional write — best effort)
    report_id = str(uuid.uuid4())
    generated_at = _now_iso()
    try:
        from src.reports.match_report_manager import MatchReportManager

        mgr = MatchReportManager(db)
        created = mgr.create_report(
            user_id=app["seeker_user_id"],
            resume_text=resume_text[:8000],
            matches=[match_item],
            title=f"投递报告 · {job_title}"[:120],
            summary=(match_item.get("reason") or "")[:1000],
            resume_id=str(resume_id),
        )
        report_id = created["id"]
        generated_at = created.get("created_at") or generated_at
        # Annotate metadata for (resume_id, job_id) cache lookup
        with db.get_conn() as conn:
            row_m = conn.execute(
                "SELECT metadata FROM match_reports WHERE id = ?", (report_id,)
            ).fetchone()
            try:
                meta = json.loads((row_m["metadata"] if row_m else None) or "{}")
            except json.JSONDecodeError:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            meta.update({
                "report_type": "application",
                "application_id": application_id,
                "job_id": str(job_id),
            })
            conn.execute(
                "UPDATE match_reports SET metadata = ?, updated_at = ? WHERE id = ?",
                (json.dumps(meta, ensure_ascii=False), _now_iso(), report_id),
            )
    except Exception as e:
        logger.warning("application report persist skipped: %s", e)

    # Build response from match_item (even if persist failed)
    scores = match_item.get("scores") or {}
    overall = float(scores.get("overall") or match_item.get("overall_score") or 0)
    if overall > 1.0:
        overall = round(overall / 100.0, 4)
    gaps = []
    for g_item in match_item.get("gap_analysis") or []:
        if isinstance(g_item, dict):
            gaps.append({
                "skill": g_item.get("skill") or "",
                "importance": g_item.get("importance") or g_item.get("priority") or "preferred",
                "suggestion": g_item.get("suggestion") or "",
            })
    plan = match_item.get("improvement_plan") or ""
    suggestions = [s.strip() for s in str(plan).split("\n") if s.strip()]
    if match_item.get("reason"):
        suggestions = [match_item["reason"]] + suggestions

    return jsonify(
        application_id=application_id,
        resume_id=str(resume_id),
        job_id=str(job_id),
        job_title=job_title,
        match_report={
            "report_id": report_id,
            "cached": False,
            "overall_score": overall,
            "skill_match": {
                "matched": match_item.get("matched_skills") or [],
                "missing": match_item.get("missing_skills") or [],
                "partial": [],
            },
            "gaps": gaps,
            "suggestions": suggestions[:8],
            "generated_at": generated_at,
        },
    )


@application_bp.route("/application/<application_id>", methods=["DELETE"])
@require_auth
def withdraw_application(application_id: str):
    """Withdraw application — HR list/detail no longer expose resume body."""
    db = _db()
    seeker = str(g.user_id)
    now = _now_iso()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not row:
            return jsonify(error="not_found", message="投递记录不存在"), 404
        if str(row["seeker_user_id"]) != seeker:
            return jsonify(error="forbidden", message="只能撤回自己的投递"), 403
        if row["status"] == "withdrawn":
            return jsonify(application=_row_to_app(row), already_withdrawn=True), 200

        conn.execute(
            """UPDATE applications
               SET status = 'withdrawn', withdrawn_at = ?, updated_at = ?
               WHERE id = ?""",
            (now, now, application_id),
        )
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()

    logger.info("application withdrawn id=%s seeker=%s", application_id, seeker)
    return jsonify(application=_row_to_app(row), already_withdrawn=False)


@application_bp.route("/jobs/<job_id>/applications", methods=["GET"])
@require_auth
def list_job_applications(job_id: str):
    """HR: list active (submitted) applications for a job, with resume summary."""
    viewer = str(g.user_id)
    db = _db()
    include_withdrawn = (request.args.get("include_withdrawn") or "").lower() in (
        "1",
        "true",
        "yes",
    )

    with db.get_conn() as conn:
        if not _can_view_as_hr(conn, viewer, job_id):
            # Job owner missing (e.g. mock id) — still allow admin/hr; else 403
            return jsonify(
                error="forbidden",
                message="无权查看该职位投递（需为职位发布者或 admin/hr）",
            ), 403

        if include_withdrawn:
            rows = conn.execute(
                """SELECT * FROM applications WHERE job_id = ?
                   ORDER BY created_at DESC LIMIT 200""",
                (job_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM applications
                   WHERE job_id = ? AND status = 'submitted'
                   ORDER BY created_at DESC LIMIT 200""",
                (job_id,),
            ).fetchall()

        items = []
        for r in rows:
            app = _row_to_app(r)
            resume_row = conn.execute(
                "SELECT title, metadata FROM documents WHERE id = ? AND doc_type = 'resume'",
                (app["resume_id"],),
            ).fetchone()
            try:
                rmeta = json.loads((resume_row["metadata"] if resume_row else None) or "{}")
            except json.JSONDecodeError:
                rmeta = {}
            include_body = app["status"] == "submitted"
            items.append({
                "application": app,
                "resume": _resume_payload_for_hr(rmeta, include_body=include_body),
                "resume_title": (resume_row["title"] if resume_row else ""),
            })

    return jsonify(job_id=job_id, applications=items, total=len(items))
