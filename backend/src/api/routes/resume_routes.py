"""
Resume routes blueprint.
Ownership: szbenyx

Endpoints:
  GET  /v1/resume/list      - List user's uploaded resumes
  GET  /v1/resume/analysis  - Get AI analysis for a specific resume
  POST /v1/resume/parse     - Parse plain resume text to structured data
  POST /v1/resume/upload    - Upload resume file (PDF/DOCX), auto-parsed via MarkItDown + LLM
  POST /v1/resume/ingest    - Ingest pre-parsed markdown directly (DemoPeter thin-ingest)
  POST /v1/resume/improve   - Generate improvement suggestions for a parsed resume
  DELETE /v1/resume/<resume_id> - Delete a resume
"""
import io
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth, optional_auth
from src.compliance.consent import require_consent
from src.utils.quota import (
    consume_with_boost,
    refund_consumption,
    QUOTA_LIMITS,
    RESOURCE_RESUME_PARSE,
    get_remaining,
    build_upgrade_hint,
)

logger = logging.getLogger("looma.resume")
resume_bp = Blueprint("resume", __name__)

# Shanghai timezone

# ── Trust Bridge: record parsed skills as trust memory ──

def _record_resume_trust(user_id: str, parsed: dict):
    """Record skills claimed from resume as trust_memories.
    Bridges the gap between 'self-claimed' resume data and 'behaviour-proven' trust data.
    """
    if user_id == "guest-anon":
        return
    try:
        from src.db.manager import DatabaseManager
        from src.agents.trust_agent import generate_attestations

        db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
        db = DatabaseManager(db_path)

        skills = parsed.get("skills") or parsed.get("tech_stack") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        db.insert_trust_memory(
            user_id=user_id,
            session_type="resume",
            session_id=f"resume_parse_{user_id}",
            memory_content={
                "skills_claimed": skills[:20],
                "roles": parsed.get("roles") or parsed.get("desired_positions") or [],
                "years": parsed.get("years_of_experience") or "",
                "education": parsed.get("highest_degree") or "",
            },
            memory_level=2,
        )
        generate_attestations(user_id, db)
        logger.info("trust_bridge: resume skills recorded for %s (%d skills)", user_id, len(skills))
    except Exception as e:
        logger.warning("trust_bridge: resume trust recording skipped for %s: %s", user_id, e)


def _record_resume_timeline(user_id: str, parsed: dict, *, channel: str, file_ext: str = "", raw_chars: int = 0):
    """Best-effort timeline resume_ingest (no full text)."""
    if user_id == "guest-anon":
        return
    try:
        from src.db.manager import DatabaseManager
        from src.timeline.events import record_resume_ingest

        db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
        db = DatabaseManager(db_path)
        skills = parsed.get("skills") or parsed.get("tech_stack") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        record_resume_ingest(
            db,
            user_id,
            source_ref=f"resume_parse_{user_id}",
            channel=channel,
            skills_count=len(skills) if isinstance(skills, list) else 0,
            years=str(parsed.get("years_of_experience") or ""),
            degree=str(parsed.get("highest_degree") or ""),
            file_ext=file_ext,
            raw_chars=raw_chars,
        )
    except Exception as e:
        logger.warning("timeline: resume_ingest skipped for %s: %s", user_id, e)

_SHA_TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_SHA_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def _quota_exceeded_response(tier: str):
    upgrade = build_upgrade_hint(tier, 0)
    return jsonify(error="quota_exceeded", message="当日简历解析配额已用尽", upgrade=upgrade), 429


@resume_bp.route("/parse", methods=["POST"])
@optional_auth
@require_consent("jobseeker_core")
def parse_resume():
    """Parse resume text to structured data."""
    data = request.get_json() or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify(error="bad_request", message="resume text required"), 400

    user_id = g.get("user_id", "guest-anon")
    tier = g.get("user_tier", "guest")

    # Quota check
    quota_result = consume_with_boost(user_id, tier, RESOURCE_RESUME_PARSE)
    if not quota_result["ok"]:
        return _quota_exceeded_response(tier)

    try:
        from src.agents.document_agents import run_document_analysis
        result = run_document_analysis("resume", text)
        if result is None:
            return jsonify(error="parse_failed", message="简历解析未返回结果"), 500

        # ── Trust Bridge: record skills_claimed from resume ──
        _record_resume_trust(user_id, result)
        _record_resume_timeline(user_id, result, channel="parse", raw_chars=len(text))

        return jsonify(extracted=result)
    except Exception as e:
        return jsonify(error="parse_failed", message=str(e)), 500


@resume_bp.route("/upload", methods=["POST"])
@optional_auth
@require_consent("jobseeker_core")
def upload_resume():
    """Upload resume file (PDF/DOCX/Word) for AI parsing.

    Pipeline:
      1. MarkItDown binary→Markdown
      2. Persist text + metadata to DB (ALWAYS — even if LLM later fails)
      3. LLM structured extraction (best-effort; updates DB metadata on success)

    Accepts multipart/form-data with field name ``file``.

    Returns ``resume_id`` always when Step 2 succeeds, with ``status: "complete" | "partial"``.
    """
    user_id = g.get("user_id", "guest-anon")
    tier = g.get("user_tier", "guest")

    # Check file presence
    if "file" not in request.files:
        return jsonify(error="bad_request", message="未检测到上传文件"), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify(error="bad_request", message="文件名称为空"), 400

    # Validate extension
    filename = file.filename
    allowed = {".pdf", ".docx", ".doc", ".txt", ".md"}
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{ext}" not in allowed:
        return jsonify(error="bad_request", message=f"不支持的文件格式: .{ext}，支持: {', '.join(allowed)}"), 400

    # Quota check
    quota_result = consume_with_boost(user_id, tier, RESOURCE_RESUME_PARSE)
    if not quota_result["ok"]:
        return _quota_exceeded_response(tier)

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
        logger.warning("Resume upload rejected (%s): %s", e.code, e)
        refund_consumption(user_id, RESOURCE_RESUME_PARSE, quota_result.get("source", "daily"))
        return jsonify(error="convert_failed", hint=e.code, message=str(e)), 422
    except Exception as e:
        logger.error(f"MarkItDown conversion failed for {filename}: {e}")
        refund_consumption(user_id, RESOURCE_RESUME_PARSE, quota_result.get("source", "daily"))
        err_text = str(e)
        if "dependencies needed to read" in err_text or "MissingDependency" in err_text:
            return jsonify(
                error="convert_failed",
                message="服务端缺少文档解析依赖，请联系管理员（PDF/DOCX 转换组件未安装）",
            ), 503
        # MarkItDown: legacy .doc often surfaces as "No converter attempted"
        if "No converter attempted" in err_text or "not supported" in err_text.lower():
            return jsonify(
                error="convert_failed",
                hint="legacy_doc_unsupported",
                message=(
                    f"「{filename}」无法解析。若为旧版 Word（.doc），请另存为 .docx 或 PDF 后重试；"
                    "若已是 .docx/.pdf，请检查文件是否损坏。"
                ),
            ), 422
        return jsonify(
            error="convert_failed",
            message=f"文档解析失败（{filename} 格式未识别或文件损坏）",
        ), 422

    if not markdown or not markdown.strip():
        refund_consumption(user_id, RESOURCE_RESUME_PARSE, quota_result.get("source", "daily"))
        return jsonify(error="convert_failed", message="文档内容为空，无法提取文字"), 422

    # Step 2: Persist text FIRST (always, even if LLM later fails)
    resume_id = None
    owner = str(user_id or "anon")
    try:
        from src.db.manager import DatabaseManager
        from werkzeug.utils import secure_filename

        db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
        db = DatabaseManager(db_path)
        safe_name = secure_filename(filename) or "resume.bin"
        provisional_path = f"resume/{owner}/{uuid.uuid4().hex}_{safe_name}"
        meta_json = json.dumps(
            {"markdown": markdown, "user_id": owner, "filename": filename},
            ensure_ascii=False,
        )
        with db.get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO documents (title, file_path, doc_type, file_size, metadata, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'uploaded', ?)""",
                (filename, provisional_path, "resume", len(content), meta_json, _now_iso()),
            )
            row_id = cur.lastrowid
            if not row_id:
                raise RuntimeError("documents insert returned no lastrowid")
            final_path = f"resume/{owner}/{row_id}_{safe_name}"
            conn.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                (final_path, row_id),
            )
            resume_id = str(row_id)
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to persist resume text: {e}")
        resume_id = None

    # Step 3: LLM structured extraction (best-effort — resume_id already exists)
    extracted = None
    extract_error = None
    extract_hint = None
    try:
        from src.agents.document_agents import DocumentAnalysisError, run_document_analysis

        extracted = run_document_analysis("resume", markdown)
    except DocumentAnalysisError as e:
        logger.error(f"Resume extraction {e.code}: {e.message}")
        extract_error = e.message
        extract_hint = e.code
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        extract_error = f"结构化提取失败: {e}"

    if extracted and resume_id:
        # Update DB metadata with extracted data
        try:
            db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
            db = DatabaseManager(db_path)
            meta_json = json.dumps(
                {"extracted": extracted, "markdown": markdown, "user_id": owner, "filename": filename},
                ensure_ascii=False,
            )
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE documents SET metadata = ?, status = 'processed' WHERE id = ?",
                    (meta_json, int(resume_id)),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update resume metadata with extracted: {e}")

        # ── Trust Bridge: record upload resume trust ──
        _record_resume_trust(user_id, extracted)
        ext = ""
        if filename and "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()[:10]
        _record_resume_timeline(
            user_id, extracted, channel="upload", file_ext=ext, raw_chars=len(markdown or ""),
        )
    elif not extracted:
        logger.warning(
            f"LLM extraction produced no result for resume upload, "
            f"filename={filename}, markdown_len={len(markdown)}, "
            f"resume_id={resume_id} (persisted as text-only)"
        )

    # Build response — always include resume_id when persisted
    response_body = {
        "extracted": extracted,
        "markdown": markdown,
        "filename": filename,
        "resume_id": resume_id,
        "status": "complete" if (extracted and resume_id) else "partial",
    }
    if extract_error:
        response_body["error"] = extract_error
    if extract_hint:
        response_body["hint"] = extract_hint

    return jsonify(response_body)


@resume_bp.route("/ingest", methods=["POST"])
@optional_auth
@require_consent("jobseeker_core")
def ingest_resume():
    """Ingest pre-parsed resume markdown directly into DB (no LLM call).

    Designed for DemoPeter terminal → Looma thin-ingest path.
    DemoPeter handles MarkItDown + LLM extraction locally;
    Looma only stores the result.

    JSON body::

        {
            "markdown":  "...",       // required, pre-parsed markdown text
            "filename":  "...",       // optional, defaults to "resume_ingest.txt"
            "extracted": { ... }      // optional, structured extraction result
        }

    Returns ``{ resume_id, status }`` where status is ``"processed"`` (has extracted)
    or ``"stored"`` (markdown only). DB ``documents.status`` uses ``processed`` / ``uploaded``.
    """
    data = request.get_json() or {}
    markdown = (data.get("markdown") or "").strip()
    filename = (data.get("filename") or "").strip() or "resume_ingest.txt"
    extracted = data.get("extracted")

    if not markdown:
        return jsonify(error="bad_request", message="markdown is required"), 400

    user_id = g.get("user_id", "guest-anon")

    try:
        from src.db.manager import DatabaseManager
        from werkzeug.utils import secure_filename

        db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
        db = DatabaseManager(db_path)
        owner = str(user_id or "anon")
        safe_name = secure_filename(filename) or "resume.bin"
        provisional_path = f"resume/{owner}/{uuid.uuid4().hex}_{safe_name}"

        meta = {"markdown": markdown, "user_id": owner, "filename": filename}
        if extracted:
            meta["extracted"] = extracted

        # API status ≠ documents.status: stored=markdown only, processed=+extracted
        api_status = "processed" if extracted else "stored"
        doc_status = "processed" if extracted else "uploaded"
        meta_json = json.dumps(meta, ensure_ascii=False)

        with db.get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO documents (title, file_path, doc_type, file_size, metadata, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    filename,
                    provisional_path,
                    "resume",
                    len(markdown.encode("utf-8")),
                    meta_json,
                    doc_status,
                    _now_iso(),
                ),
            )
            row_id = cur.lastrowid
            if not row_id:
                raise RuntimeError("documents insert returned no lastrowid")
            final_path = f"resume/{owner}/{row_id}_{safe_name}"
            conn.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                (final_path, row_id),
            )
            resume_id = str(row_id)

        # ── Trust Bridge: record ingest resume trust ──
        if extracted and user_id != "guest-anon":
            _record_resume_trust(user_id, extracted)
            _record_resume_timeline(user_id, extracted, channel="ingest", raw_chars=len(markdown))

        return jsonify(resume_id=resume_id, status=api_status)

    except Exception as e:
        logger.error(f"Failed to ingest resume: {e}")
        return jsonify(error="server_error", message=f"入库失败: {e}"), 500


@resume_bp.route("/improve", methods=["POST"])
@optional_auth
@require_consent("jobseeker_core")
def improve_resume():
    """Generate AI-powered improvement suggestions for a resume.

    Accepts JSON body with either:
      - ``resume_text``: raw resume text (plain or markdown)
      - ``extracted``:   already-parsed resume JSON
      - ``focus``:       optional — which area to focus on ("overall" | "skills" | "experience" | "education")
    """
    data = request.get_json() or {}
    resume_text = data.get("resume_text", "").strip()
    extracted = data.get("extracted")
    focus = data.get("focus", "overall").strip().lower()

    if not resume_text and not extracted:
        return jsonify(error="bad_request", message="请提供简历文本(resume_text)或已解析数据(extracted)"), 400

    # Build input for LLM
    if resume_text:
        text_for_prompt = resume_text[:4000]
    else:
        text_for_prompt = json.dumps(extracted, ensure_ascii=False, indent=2)[:4000]

    focus_hints = {
        "overall": "请从整体结构、内容完整度、关键信息呈现、语言表达等方面给出建议",
        "skills": "请重点分析技能描述是否充分、与目标岗位的匹配度、技能分类是否合理",
        "experience": "请重点分析工作/项目经历的写法是否突出了成果和量化指标，描述是否具体",
        "education": "请重点分析教育背景的呈现方式、与岗位要求的关联度",
    }
    focus_prompt = focus_hints.get(focus, focus_hints["overall"])

    prompt = (
        "你是一位资深HR和简历优化专家。请仔细分析以下简历内容，给出具体可操作的改进建议。\n\n"
        f"分析维度：{focus_prompt}\n\n"
        "请输出 JSON 格式：\n"
        "{\n"
        '  "overall_score": 数字(0-100),\n'
        '  "strengths": ["优点1", "优点2"],\n'
        '  "weaknesses": ["需改进的地方1", "需要改进的地方2"],\n'
        '  "suggestions": [\n'
        '    {"area": "区域", "issue": "问题", "advice": "具体操作建议", "example": "改后示例"}\n'
        '  ],\n'
        '  "summary": "总结性建议"\n'
        "}\n\n"
        f"简历内容：\n{text_for_prompt}"
    )

    try:
        from src.agents.central_brain import _call_llm
        import re as _re

        response = _call_llm(prompt)
        if not response:
            return jsonify(error="llm_failed", message="AI 分析服务暂不可用，请稍后重试"), 503

        resp = response.strip()
        if "```" in resp:
            m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", resp)
            if m:
                resp = m.group(1).strip()
        parsed = json.loads(resp)
        return jsonify(improvements=parsed)
    except json.JSONDecodeError:
        return jsonify(error="llm_parse_failed", message="AI 返回格式异常，请重试"), 500
    except Exception as e:
        logger.error(f"Resume improve failed: {e}")
        return jsonify(error="improve_failed", message=str(e)), 500


# ── HarmonyOS 对齐端点 ──


@resume_bp.route("/list", methods=["GET"])
@require_auth
def list_resumes():
    """List all resumes uploaded by the current user.

    Returns resumes stored in the documents table with doc_type='resume'.
    """
    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
    from src.db.manager import DatabaseManager
    db = DatabaseManager(db_path)
    user_id = str(g.get("user_id") or "")

    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, title, file_path, file_size, metadata, created_at
                   FROM documents
                   WHERE doc_type = 'resume'
                     AND json_extract(metadata, '$.user_id') = ?
                   ORDER BY created_at DESC LIMIT 50""",
                (user_id,),
            ).fetchall()
    except Exception as e:
        logger.error(f"Failed to list resumes: {e}")
        return jsonify(resumes=[], total=0)

    resumes = []
    for r in rows:
        meta = json.loads(r["metadata"] or "{}")
        extracted = meta.get("extracted") or {}
        resumes.append({
            "id": str(r["id"]),
            "title": r["title"] or "未命名简历",
            "filename": r["title"] or r["file_path"],
            "file_size": r["file_size"],
            "uploaded_at": r["created_at"],
            "extracted": extracted,
        })

    return jsonify(resumes=resumes, total=len(resumes))


@resume_bp.route("/analysis", methods=["GET"])
@require_auth
def analysis_resume():
    """Get AI analysis summary for a specific resume.

    Query: ?resume_id=xxx
    """
    resume_id = (request.args.get("resume_id") or "").strip()
    if not resume_id:
        return jsonify(error="bad_request", message="resume_id required"), 400

    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
    from src.db.manager import DatabaseManager
    db = DatabaseManager(db_path)
    user_id = str(g.get("user_id") or "")

    try:
        with db.get_conn() as conn:
            row = conn.execute(
                """SELECT id, title, file_path, metadata, created_at
                   FROM documents
                   WHERE id = ? AND doc_type = 'resume'
                     AND json_extract(metadata, '$.user_id') = ?""",
                (resume_id, user_id),
            ).fetchone()
    except Exception as e:
        logger.error(f"Failed to load resume for analysis: {e}")
        return jsonify(error="not_found", message="简历不存在"), 404

    if not row:
        return jsonify(error="not_found", message="简历不存在"), 404

    meta = json.loads(row["metadata"] or "{}")
    extracted = meta.get("extracted") or {}
    markdown_text = meta.get("markdown", "")[:4000]

    # Generate analysis via LLM
    try:
        from src.agents.central_brain import _call_llm
        import re as _re

        prompt = (
            "你是一位资深HR。请分析以下简历，给出综合评估。"
            "输出 JSON 格式：\n"
            "{\n"
            '  "overall_score": 数字(0-100),\n'
            '  "strengths": ["优势1", "优势2"],\n'
            '  "weaknesses": ["不足1", "不足2"],\n'
            '  "suggestions": ["建议1", "建议2"],\n'
            '  "matched_roles": ["适合岗位1"],\n'
            '  "summary": "综合评语"\n'
            "}\n\n"
            f"简历内容：\n{markdown_text}"
        )

        response = _call_llm(prompt)
        if response:
            resp = response.strip()
            if "```" in resp:
                m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", resp)
                if m:
                    resp = m.group(1).strip()
            analysis = json.loads(resp)
        else:
            analysis = None
    except Exception as e:
        logger.warning(f"Resume analysis LLM failed: {e}")
        analysis = None

    return jsonify(
        resume_id=str(row["id"]),
        title=row["title"],
        extracted=extracted,
        markdown=markdown_text,
        analysis=analysis,
    )


@resume_bp.route("/<resume_id>", methods=["DELETE"])
@require_auth
def delete_resume(resume_id: str):
    """Delete a resume by ID (owner-scoped)."""
    db_path = current_app.config.get("DATABASE_PATH", "data/looma.db")
    from src.db.manager import DatabaseManager
    db = DatabaseManager(db_path)
    user_id = str(g.get("user_id") or "")

    try:
        with db.get_conn() as conn:
            cur = conn.execute(
                """DELETE FROM documents
                   WHERE id = ? AND doc_type = 'resume'
                     AND json_extract(metadata, '$.user_id') = ?""",
                (resume_id, user_id),
            )
            if cur.rowcount == 0:
                return jsonify(error="not_found", message="简历不存在"), 404
    except Exception as e:
        logger.error(f"Failed to delete resume {resume_id}: {e}")
        return jsonify(error="delete_failed", message=str(e)), 500

    return jsonify(message="deleted", resume_id=resume_id)
