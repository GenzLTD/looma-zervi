"""
Jobs routes blueprint.
Ownership: szbenyx

Endpoints:
  GET  /v1/jobs/          - List jobs (alias of /list, for HarmonyOS)
  GET  /v1/jobs/list      - List persisted jobs (fallback to mock)
  GET  /v1/jobs/search    - Search jobs by keyword
  GET  /v1/jobs/recommend - AI-recommended jobs for current user
  GET  /v1/jobs/<job_id>  - Get job detail by ID
  POST /v1/jobs/upload    - Upload JD file (PDF/DOCX), auto-parsed via MarkItDown + LLM
  POST /v1/jobs/parse     - Parse plain job description text to structured data
  POST /v1/jobs/match     - Match resume to job listings via multi-dimension LLM scoring
"""
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth, optional_auth
from src.compliance.consent import require_consent
from src.utils.quota import consume_with_boost, RESOURCE_JOB_MATCH, build_upgrade_hint

logger = logging.getLogger("looma.jobs")
jobs_bp = Blueprint("jobs", __name__)

_SHA_TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_SHA_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def _quota_exceeded_response(tier: str):
    upgrade = build_upgrade_hint(tier, 0)
    return jsonify(error="quota_exceeded", message="当日职位匹配配额已用尽", upgrade=upgrade), 429


# ── Trust Bridge: record match results as trust memory ──

def _record_match_trust(user_id: str, matches: list[dict]):
    """Record job match interaction as trust_memories.
    Bridges the gap between 'matching behaviour' and 'trust profile'.
    """
    if not user_id or not matches:
        return
    try:
        from src.db.manager import DatabaseManager
        from src.agents.trust_agent import generate_attestations

        db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
        db = DatabaseManager(db_path)

        top = matches[0]
        db.insert_trust_memory(
            user_id=user_id,
            session_type="match",
            session_id=f"job_match_{user_id}",
            memory_content={
                "top_job": top.get("title", ""),
                "top_company": top.get("company", ""),
                "top_score": top.get("scores", {}).get("overall", 0),
                "matched_skills": top.get("matched_skills", []),
                "total_jobs_matched": len(matches),
            },
            memory_level=1,
        )
        generate_attestations(user_id, db)
        logger.info("trust_bridge: match trust recorded for %s (top: %s, score: %s)",
                     user_id, top.get("title"), top.get("scores", {}).get("overall"))
    except Exception as e:
        logger.warning("trust_bridge: match trust recording skipped for %s: %s", user_id, e)


# ── Mock jobs (fallback when no persisted jobs) ──
MOCK_JOBS = [
    {"id": "j1", "title": "前端开发工程师", "company": "字节跳动", "location": "深圳",
     "salary_range": "25-40K", "description": "负责抖音前端开发，React/Vue"},
    {"id": "j2", "title": "Python 后端开发", "company": "腾讯", "location": "深圳",
     "salary_range": "20-35K", "description": "微服务架构开发，FastAPI/Django"},
    {"id": "j3", "title": "AI 算法工程师", "company": "华为", "location": "深圳",
     "salary_range": "30-50K", "description": "NLP/推荐系统算法研发"},
    {"id": "j4", "title": "产品经理", "company": "阿里", "location": "杭州",
     "salary_range": "25-45K", "description": "电商产品规划与迭代"},
    {"id": "j5", "title": "数据分析师", "company": "美团", "location": "北京",
     "salary_range": "20-30K", "description": "业务数据分析与可视化"},
]


def _is_overseas_deploy() -> bool:
    """SG/US regions skip mainland demo job fixtures."""
    region = (current_app.config.get("DEPLOY_REGION") or "US").upper()
    return region in ("SG", "US")


def _fallback_jobs() -> list[dict]:
    if _is_overseas_deploy():
        return []
    return MOCK_JOBS


def _persist_job(
    *,
    user_id: str,
    title: str,
    file_path: str,
    file_size: int,
    parsed: dict | None,
    markdown: str,
    source: str,
) -> str:
    """Persist a job document with a stable job_id in metadata; return job_id."""
    from src.db.manager import DatabaseManager

    job_id = str(uuid.uuid4())
    parsed_out = dict(parsed or {})
    parsed_out["id"] = job_id
    if not parsed_out.get("source"):
        parsed_out["source"] = source

    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
    db = DatabaseManager(db_path)
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO documents (title, file_path, doc_type, file_size, metadata, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'processed', ?)""",
            (
                title or parsed_out.get("title") or "未命名职位",
                file_path,
                "job",
                file_size,
                json.dumps(
                    {
                        "job_id": job_id,
                        "parsed": parsed_out,
                        "markdown": markdown,
                        "user_id": user_id,
                        "source": source,
                    },
                    ensure_ascii=False,
                ),
                _now_iso(),
            ),
        )
    return job_id


def _job_from_row(r) -> dict:
    meta = json.loads(r["metadata"] or "{}")
    parsed = meta.get("parsed") or {}
    job_id = meta.get("job_id") or parsed.get("id") or f"doc-{r['id']}"
    # Prefer full source markdown for matching when richer than LLM summary
    summary = parsed.get("description") or ""
    markdown = meta.get("markdown") or ""
    description = markdown if len(markdown) >= len(summary) else summary
    if isinstance(description, str) and len(description) > 4000:
        description = description[:4000]
    return {
        "id": job_id,
        "title": parsed.get("title") or r["title"],
        "company": parsed.get("company") or "",
        "location": parsed.get("location") or "",
        "salary_range": parsed.get("salary_range") or "",
        "description": description,
        "requirements": parsed.get("requirements") or [],
        "tags": parsed.get("tags") or [],
        "posted_at": parsed.get("posted_at") or r["created_at"],
        "url": parsed.get("url") or "",
        "source": parsed.get("source") or meta.get("source") or "upload",
    }


def _get_persisted_jobs() -> list[dict]:
    """Read all persisted jobs from DB."""
    try:
        from src.db.manager import DatabaseManager

        db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
        db = DatabaseManager(db_path)
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, title, file_path, doc_type, file_size, metadata, created_at
                   FROM documents WHERE doc_type = 'job' AND status = 'processed'
                   ORDER BY created_at DESC LIMIT 50"""
            ).fetchall()
        if rows:
            return [_job_from_row(r) for r in rows]
    except Exception as e:
        logger.warning(f"Failed to read persisted jobs: {e}")
    return []


# ── Endpoints ──


@jobs_bp.route("/list", methods=["GET"])
@optional_auth
def list_jobs():
    """List available jobs: persisted first, then mock fallback."""
    persisted = _get_persisted_jobs()
    if persisted:
        return jsonify(jobs=persisted, total=len(persisted))
    fallback = _fallback_jobs()
    return jsonify(jobs=fallback, total=len(fallback))


@jobs_bp.route("/upload", methods=["POST"])
@optional_auth
def upload_job():
    """Upload a job description file (PDF/DOCX) for AI parsing.

    Pipeline: MarkItDown binary→Markdown → LLM structured extraction → persist → return.
    Accepts multipart/form-data with field name ``file``.
    """
    user_id = g.get("user_id", "guest-anon")

    if "file" not in request.files:
        return jsonify(error="bad_request", message="未检测到上传文件"), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify(error="bad_request", message="文件名称为空"), 400

    filename = file.filename
    allowed = {".pdf", ".docx", ".doc", ".txt", ".md"}
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{ext}" not in allowed:
        return jsonify(error="bad_request", message=f"不支持的文件格式: .{ext}，支持: {', '.join(allowed)}"), 400

    # Read file bytes
    try:
        content = file.read()
    except Exception as e:
        return jsonify(error="read_failed", message=f"文件读取失败: {e}"), 400

    if not content:
        return jsonify(error="read_failed", message="文件内容为空"), 400

    # Step 1: MarkItDown conversion (PDF/DOCX → Markdown)
    try:
        from src.ingest.markitdown_convert import UnsupportedDocumentFormat, bytes_to_markdown

        markdown = bytes_to_markdown(content, filename=filename)
    except UnsupportedDocumentFormat as e:
        logger.warning("Job upload rejected (%s): %s", e.code, e)
        return jsonify(error="convert_failed", hint=e.code, message=str(e)), 422
    except Exception as e:
        logger.error(f"MarkItDown conversion failed for {filename}: {e}")
        err_text = str(e)
        if "No converter attempted" in err_text or "not supported" in err_text.lower():
            return jsonify(
                error="convert_failed",
                hint="legacy_doc_unsupported",
                message=(
                    f"「{filename}」无法解析。若为旧版 Word（.doc），请另存为 .docx 或 PDF 后重试；"
                    "若已是 .docx/.pdf，请检查文件是否损坏。"
                ),
            ), 422
        return jsonify(error="convert_failed", message=f"文档解析失败（{filename} 格式未识别或文件损坏）"), 422

    if not markdown or not markdown.strip():
        return jsonify(error="convert_failed", message="文档内容为空，无法提取文字"), 422

    # Step 2: LLM structured extraction
    try:
        from src.agents.document_agents import DocumentAnalysisError, run_document_analysis

        parsed = run_document_analysis("job", markdown)
    except DocumentAnalysisError as e:
        logger.error(f"Job extraction {e.code}: {e.message}")
        return jsonify(
            parsed=None,
            markdown=markdown,
            filename=filename,
            error=e.message,
            hint="resume_not_jd" if e.code == "parse_failed" else e.code,
        ), 200
    except Exception as e:
        logger.error(f"LLM extraction failed for job: {e}")
        return jsonify(
            parsed=None,
            markdown=markdown,
            filename=filename,
            error=f"结构化提取失败: {e}",
        ), 200

    if not parsed:
        logger.warning(f"LLM returned empty result for job upload, filename={filename}, markdown_len={len(markdown)}")
        return jsonify(
            parsed=None,
            markdown=markdown,
            filename=filename,
            error="结构化提取失败: LLM 未能返回有效的 JD 解析结果，请确认上传的是职位描述文件（非简历）。如需上传简历请使用「简历解析」功能。",
            hint="resume_not_jd",
        ), 200

    # Step 3: Persist to DB (stable job_id in metadata)
    job_id = None
    try:
        path_key = f"upload/{uuid.uuid4().hex}/{filename}"
        job_id = _persist_job(
            user_id=user_id,
            title=parsed.get("title") or filename,
            file_path=path_key,
            file_size=len(content),
            parsed=parsed,
            markdown=markdown,
            source="upload",
        )
        parsed = {**parsed, "id": job_id, "source": parsed.get("source") or "upload"}
    except Exception as e:
        logger.warning(f"Failed to persist job: {e}")

    return jsonify(
        parsed=parsed,
        markdown=markdown,
        filename=filename,
        job_id=job_id,
    )


@jobs_bp.route("/parse", methods=["POST"])
@optional_auth
def parse_job():
    """Parse plain job description text, persist to job pool, return structured data."""
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    user_id = g.get("user_id", "guest-anon")

    if not text:
        return jsonify(error="bad_request", message="请输入职位描述文本"), 400

    try:
        from src.agents.document_agents import run_document_analysis
        parsed = run_document_analysis("job", text)
        if parsed is None:
            return jsonify(error="parse_failed", message="职位解析未返回结果"), 500
    except Exception as e:
        return jsonify(error="parse_failed", message=str(e)), 500

    job_id = None
    try:
        path_key = f"parse/{uuid.uuid4().hex}.txt"
        job_id = _persist_job(
            user_id=user_id,
            title=parsed.get("title") or "粘贴解析职位",
            file_path=path_key,
            file_size=len(text.encode("utf-8")),
            parsed=parsed,
            markdown=text,
            source="paste",
        )
        parsed = {**parsed, "id": job_id, "source": parsed.get("source") or "paste"}
    except Exception as e:
        logger.warning(f"Failed to persist parsed job: {e}")

    return jsonify(parsed=parsed, job_id=job_id, markdown=text)


@jobs_bp.route("/match", methods=["POST"])
@optional_auth
@require_consent("jobseeker_core")
def job_match():
    """Match a resume to job listings via multi-dimension LLM scoring.

    Accepts JSON body:
      - resume_text:        resume content (required)
      - job_id:             optional — match against a single persisted job
      - job_description:    optional — match against ad-hoc job text
    """
    data = request.get_json() or {}
    resume_text = data.get("resume_text", "").strip()

    if not resume_text:
        return jsonify(error="bad_request", message="resume_text required"), 400

    user_id = g.get("user_id", "guest-anon")
    tier = g.get("user_tier", "guest")

    # Determine job source before consuming quota
    target_jobs = []
    job_id_filter = data.get("job_id", "").strip()
    adhoc_description = data.get("job_description", "").strip()

    if adhoc_description:
        # Match against a single ad-hoc job description (optional structured hints)
        adhoc_title = (data.get("job_title") or "").strip()
        adhoc_company = (data.get("job_company") or "").strip()
        target_jobs = [{
            "id": "adhoc",
            "title": adhoc_title,
            "company": adhoc_company,
            "location": (data.get("job_location") or "").strip(),
            "salary_range": (data.get("job_salary_range") or "").strip(),
            "description": adhoc_description,
        }]
    elif job_id_filter:
        # Match against a single persisted job
        persisted = _get_persisted_jobs()
        target_jobs = [j for j in persisted if j["id"] == job_id_filter]
        if not target_jobs:
            # Try mock
            target_jobs = [j for j in _fallback_jobs() if j["id"] == job_id_filter]
        if not target_jobs:
            return jsonify(error="not_found", message=f"职位 {job_id_filter} 不存在"), 404
    else:
        # Match against all available jobs
        persisted = _get_persisted_jobs()
        target_jobs = persisted if persisted else _fallback_jobs()

    if not target_jobs:
        return jsonify(
            error="no_jobs",
            message="暂无职位可匹配：请先在「上传JD」解析/上传职位，或指定 job_description",
            matches=[],
            total_evaluated=0,
        ), 400

    # Quota check
    quota_result = consume_with_boost(user_id, tier, RESOURCE_JOB_MATCH)
    if not quota_result["ok"]:
        return _quota_exceeded_response(tier)

    try:
        from src.pipeline.job_match_pipeline import run_job_match_pipeline
        matches, total = run_job_match_pipeline(
            resume_text=resume_text,
            jobs=target_jobs,
        )

        # ── Trust Bridge: record match interaction ──
        if user_id and user_id != "guest-anon" and matches:
            _record_match_trust(user_id, matches)
            # Timeline: job match scan (Harmony / Web 求职主路径)
            try:
                from src.timeline.events import record_match_scan
                scores = [
                    float(m.get("overall_score") or m.get("match_score") or 0)
                    for m in matches
                ]
                record_match_scan(
                    current_app._db,
                    user_id,
                    report_id=f"jobs_match_{user_id}_{int(time.time())}",
                    total_jobs=total,
                    max_score=max(scores) if scores else 0.0,
                    avg_score=(sum(scores) / len(scores)) if scores else 0.0,
                    pipeline_version="jobs_match",
                    has_resume_id=False,
                )
            except Exception as e:
                logger.warning("timeline: match_scan skipped for %s: %s", user_id, e)

        return jsonify(matches=matches, total_evaluated=total)
    except Exception as e:
        logger.error(f"Job match failed: {e}")
        return jsonify(error="match_failed", message=str(e)), 500


# ── HarmonyOS 对齐端点 ──


@jobs_bp.route("/", methods=["GET"], strict_slashes=False)
@optional_auth
def list_jobs_root():
    """List available jobs (HarmonyOS alias for /list)."""
    return list_jobs()


@jobs_bp.route("/search", methods=["GET"])
@optional_auth
def search_jobs():
    """Search jobs by keyword query parameter.

    Query: ?q=前端&location=深圳&page=1&size=20
    """
    q = (request.args.get("q") or "").strip().lower()
    location = (request.args.get("location") or "").strip().lower()
    if not q and not location:
        # No filter → return all
        return list_jobs()

    persisted = _get_persisted_jobs()
    source = persisted if persisted else _fallback_jobs()

    filtered = []
    for j in source:
        title = (j.get("title") or "").lower()
        company = (j.get("company") or "").lower()
        desc = (j.get("description") or "").lower()
        loc = (j.get("location") or "").lower()
        tags_text = " ".join(j.get("tags") or []) if j.get("tags") else ""

        matches = True
        if q:
            matches = q in title or q in company or q in desc or q in tags_text
        if matches and location:
            matches = location in loc

        if matches:
            filtered.append(j)

    return jsonify(jobs=filtered, total=len(filtered))


@jobs_bp.route("/seed-demo", methods=["POST"])
@require_auth
def seed_demo_jobs():
    """Persist demo jobs owned by the current user (for HR apply visibility).

    Idempotent: skips job_ids that already exist in documents.
    Body optional: ``{ "jobs": [ {id,title,company,...} ] }`` — defaults to MOCK_JOBS.
    """
    user_id = str(g.user_id)
    data = request.get_json(silent=True) or {}
    raw_jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else MOCK_JOBS

    from src.db.manager import DatabaseManager

    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
    db = DatabaseManager(db_path)
    created = []
    skipped = []

    with db.get_conn() as conn:
        existing_ids = set()
        for r in conn.execute(
            "SELECT metadata FROM documents WHERE doc_type = 'job'"
        ).fetchall():
            try:
                meta = json.loads(r["metadata"] or "{}")
            except json.JSONDecodeError:
                continue
            jid = meta.get("job_id") or (meta.get("parsed") or {}).get("id")
            if jid:
                existing_ids.add(str(jid))

        for j in raw_jobs:
            job_id = str(j.get("id") or uuid.uuid4())
            if job_id in existing_ids:
                skipped.append(job_id)
                continue
            title = j.get("title") or "未命名职位"
            parsed = {
                "id": job_id,
                "title": title,
                "company": j.get("company") or "",
                "location": j.get("location") or "",
                "salary_range": j.get("salary_range") or "",
                "description": j.get("description") or "",
                "source": "seed-demo",
            }
            file_path = f"job/{user_id}/{job_id}.md"
            conn.execute(
                """INSERT INTO documents
                   (title, file_path, doc_type, file_size, metadata, status, created_at)
                   VALUES (?, ?, 'job', ?, ?, 'processed', ?)""",
                (
                    title,
                    file_path,
                    len((j.get("description") or "").encode("utf-8")),
                    json.dumps(
                        {
                            "job_id": job_id,
                            "parsed": parsed,
                            "markdown": j.get("description") or title,
                            "user_id": user_id,
                            "source": "seed-demo",
                        },
                        ensure_ascii=False,
                    ),
                    _now_iso(),
                ),
            )
            created.append(job_id)
            existing_ids.add(job_id)

    return jsonify(
        created=created,
        skipped=skipped,
        total_created=len(created),
        owner_user_id=user_id,
    )


# 注意：/recommend 必须注册在 /<job_id> 之前，否则 "recommend" 会
# 被 Flask 当作 job_id 捕获，导致 404。
@jobs_bp.route("/recommend", methods=["GET"])
@require_auth
def recommend_jobs():
    """AI-recommended jobs for the current user.

    Currently returns top-scored mock jobs; future: personalization via user profile.
    """
    # Build a simple sorted list with simulated match_score
    persisted = _get_persisted_jobs()
    source = persisted if persisted else _fallback_jobs()

    # Simulate match scores based on job index (MVP)
    import random
    random.seed(g.user_id)
    scored = []
    for j in source:
        j_copy = dict(j)
        j_copy["match_score"] = random.randint(60, 99)
        scored.append(j_copy)

    scored.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    top = scored[:10]

    return jsonify(jobs=top, total=len(top))


@jobs_bp.route("/<job_id>", methods=["GET"])
@optional_auth
def job_detail(job_id: str):
    """Get job detail by ID (HarmonyOS JobDetailPage)."""
    persisted = _get_persisted_jobs()
    source = persisted if persisted else _fallback_jobs()

    for j in source:
        if j.get("id") == job_id:
            return jsonify(job=j)

    return jsonify(error="not_found", message=f"Job {job_id} not found"), 404
