"""
Job Match Pipeline — Match resumes to job listings with multi-dimension LLM scoring.

Migrated from Tatha's scoring engine.  Uses _call_llm() with structured prompts
for 11-dimension scoring (钱多事少离家近 + 技能/经验/职级/公司吸引力等).
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("looma.job_match")


def _score_resume_vs_job(resume_text: str, job_info: dict) -> dict:
    """Score one resume against one job description via LLM.

    Returns a dict with multi-dimension scores matching Tatha's JobMatchScore schema.
    """
    from src.agents.central_brain import _call_llm

    title = job_info.get("title", "")
    company = job_info.get("company", "")
    location = job_info.get("location", "")
    description = job_info.get("description", "") or f"{title} @ {company}"
    salary_range = job_info.get("salary_range", "")

    # Build rich job description for scoring
    jd_parts = [description]
    if location:
        jd_parts.insert(0, f"工作地点：{location}")
    if salary_range:
        jd_parts.insert(0, f"薪资范围：{salary_range}")
    if company:
        jd_parts.insert(0, f"公司：{company}")
    if title:
        jd_parts.insert(0, f"职位：{title}")

    jd_text = "\n".join(jd_parts)

    prompt = (
        "你是职业成长合伙人 Tatha 引擎，请分析「简历」与「职位描述」的匹配度。"
        "只输出结构化 JSON，不要任何解释或前缀。\n\n"
        "维度与范围：\n"
        "- background_match: 领域/背景匹配 0–10\n"
        "- skills_overlap: 技能重叠 0–30\n"
        "- experience_relevance: 经历相关性 0–30\n"
        "- seniority: 职级匹配 0–10\n"
        "- language_requirement: 语言要求匹配 0–10\n"
        "- company_score: 公司/岗位吸引力 0–10\n"
        "- salary_match: 薪资匹配 0–10，未提及则 5\n"
        "- location_match: 地点匹配 0–10，未提及则 5\n"
        "- culture_workload_match: 文化/强度匹配 0–10，未提及则 5\n"
        "- overall: 综合分 0–100，为各项加权综合\n"
        "- summary: 一句话匹配摘要（30字以内）\n"
        "- keywords: 已匹配技能/关键词列表（3-8个）\n"
        "- fit_bullets: 匹配要点列表（3-5条，每条15字以内）\n"
        "- missing_skills: 缺失或偏弱的关键技能名称列表（0-6个）\n"
        "- gap_analysis: 技能差距分析数组（0-5项），每项含 "
        "skill / current_level / required_level / gap / suggestion / "
        "estimated_effort / priority(high|medium|low)\n"
        "- improvement_plan: 必填。针对该职位的个性化提升计划 Markdown 短文"
        "（至少 3 条可执行步骤，结合 gap_analysis；禁止空字符串）\n\n"
        "输出格式：\n"
        "{\n"
        '  "overall": 85,\n'
        '  "background_match": 8,\n'
        '  "skills_overlap": 25,\n'
        '  "experience_relevance": 25,\n'
        '  "seniority": 8,\n'
        '  "language_requirement": 8,\n'
        '  "company_score": 7,\n'
        '  "salary_match": 6,\n'
        '  "location_match": 7,\n'
        '  "culture_workload_match": 5,\n'
        '  "summary": "技能高度匹配，地点便利，薪资有竞争力",\n'
        '  "keywords": ["Python", "FastAPI", "NLP"],\n'
        '  "fit_bullets": ["技能高度重叠", "行业背景匹配", "地点便利"],\n'
        '  "missing_skills": ["分布式事务", "系统设计"],\n'
        '  "gap_analysis": [\n'
        '    {"skill":"分布式事务","current_level":"了解概念",'
        '"required_level":"能独立设计方案","gap":"缺少生产实战",'
        '"suggestion":"学习2PC/TCC/Saga并完成Demo",'
        '"estimated_effort":"2-4周","priority":"high"}\n'
        "  ],\n"
        '  "improvement_plan": "### 提升路径\\n'
        '1. **分布式事务**（高优先，2-4周）：完成 TCC/Saga Demo 并写入简历\\n'
        '2. **系统设计**（中优先）：补齐高并发案例\\n'
        '3. **作品沉淀**：用项目量化成果准备面试故事"\n'
        "}\n\n"
        "重要：JSON 必须包含非空的 improvement_plan 字段。\n\n"
        f"【简历内容】\n{resume_text[:4000]}\n\n"
        f"【职位描述】\n{jd_text[:4000]}\n\n"
        "请输出完整 JSON（含 improvement_plan）："
    )

    try:
        response = _call_llm(prompt)
    except Exception as e:
        logger.warning(f"LLM call failed for job scoring: {e}")
        return _default_score()

    if not response:
        return _default_score()

    resp = response.strip()
    if "```" in resp:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp)
        if m:
            resp = m.group(1).strip()

    try:
        scores = json.loads(resp)
        return _sanitize_scores(scores)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON for job scoring, using defaults")
        return _default_score()


def _sanitize_gap_item(item: object) -> dict | None:
    """Normalize one gap_analysis entry; drop invalid objects."""
    if not isinstance(item, dict):
        return None
    skill = str(item.get("skill") or "").strip()
    if not skill:
        return None
    priority = str(item.get("priority") or "medium").lower()
    if priority not in ("high", "medium", "low"):
        priority = "medium"
    return {
        "skill": skill,
        "current_level": str(item.get("current_level") or "").strip(),
        "required_level": str(item.get("required_level") or "").strip(),
        "gap": str(item.get("gap") or "").strip(),
        "suggestion": str(item.get("suggestion") or "").strip(),
        "estimated_effort": str(item.get("estimated_effort") or "").strip(),
        "priority": priority,
    }


_PRIORITY_LABEL = {"high": "高", "medium": "中", "low": "低"}


def _derive_improvement_plan(
    gap_analysis: list[dict],
    missing_skills: list[str],
    summary: str,
) -> str:
    """Build a Markdown plan when LLM omits or truncates improvement_plan."""
    lines = ["### 提升路径"]
    if summary:
        lines.append(f"> {summary}")
        lines.append("")

    ordered = sorted(
        gap_analysis,
        key=lambda g: {"high": 0, "medium": 1, "low": 2}.get(g.get("priority", "medium"), 1),
    )
    if ordered:
        for i, g in enumerate(ordered[:5], 1):
            skill = g.get("skill") or "关键能力"
            pri = _PRIORITY_LABEL.get(g.get("priority", "medium"), "中")
            effort = g.get("estimated_effort") or "按周推进"
            suggestion = g.get("suggestion") or g.get("gap") or "针对岗位要求补齐实践与作品"
            lines.append(f"{i}. **{skill}**（优先：{pri}，周期：{effort}）：{suggestion}")
    elif missing_skills:
        for i, skill in enumerate(missing_skills[:5], 1):
            lines.append(f"{i}. **{skill}**：对照 JD 补齐学习路径，并形成可展示的项目/案例。")
    else:
        lines.append("1. 对照职位要求梳理技能差距，优先补齐核心硬技能。")
        lines.append("2. 用 1–2 个可量化项目沉淀作品，写入简历与面试故事。")
        lines.append("3. 针对目标公司准备岗位相关问题与案例表达。")

    lines.append("")
    lines.append("完成上述步骤后，可再次匹配该职位以复查提升效果。")
    return "\n".join(lines).strip()[:2000]


def _sanitize_scores(raw: dict) -> dict:
    """Clamp all score fields to valid ranges and fill in defaults."""
    def _clamp(val, lo, hi, default=None):
        try:
            v = int(float(val))
            return max(lo, min(hi, v))
        except (TypeError, ValueError):
            return default if default is not None else lo

    keywords = raw.get("keywords") if isinstance(raw.get("keywords"), list) else []
    fit_bullets = raw.get("fit_bullets") if isinstance(raw.get("fit_bullets"), list) else []
    missing_skills = (
        raw.get("missing_skills") if isinstance(raw.get("missing_skills"), list) else []
    )
    missing_skills = [str(s).strip() for s in missing_skills if str(s).strip()][:6]

    gap_raw = raw.get("gap_analysis") if isinstance(raw.get("gap_analysis"), list) else []
    gap_analysis = []
    for item in gap_raw[:5]:
        cleaned = _sanitize_gap_item(item)
        if cleaned:
            gap_analysis.append(cleaned)

    # Derive missing_skills from gap_analysis when LLM omitted the list
    if not missing_skills and gap_analysis:
        missing_skills = [g["skill"] for g in gap_analysis]

    summary = raw.get("summary", "") if isinstance(raw.get("summary"), str) else ""

    improvement_plan = raw.get("improvement_plan")
    if not isinstance(improvement_plan, str):
        improvement_plan = ""
    improvement_plan = improvement_plan.strip()
    if not improvement_plan:
        improvement_plan = _derive_improvement_plan(gap_analysis, missing_skills, summary)

    return {
        "overall":                _clamp(raw.get("overall"), 0, 100, 50),
        "background_match":        _clamp(raw.get("background_match"), 0, 10, 5),
        "skills_overlap":          _clamp(raw.get("skills_overlap"), 0, 30, 15),
        "experience_relevance":    _clamp(raw.get("experience_relevance"), 0, 30, 15),
        "seniority":               _clamp(raw.get("seniority"), 0, 10, 5),
        "language_requirement":    _clamp(raw.get("language_requirement"), 0, 10, 5),
        "company_score":           _clamp(raw.get("company_score"), 0, 10, 5),
        "salary_match":            _clamp(raw.get("salary_match"), 0, 10, 5),
        "location_match":          _clamp(raw.get("location_match"), 0, 10, 5),
        "culture_workload_match":  _clamp(raw.get("culture_workload_match"), 0, 10, 5),
        "summary":                 summary,
        "keywords":                [str(k) for k in keywords if str(k).strip()][:8],
        "fit_bullets":             [str(b) for b in fit_bullets if str(b).strip()][:5],
        "missing_skills":          missing_skills,
        "gap_analysis":            gap_analysis,
        "improvement_plan":        improvement_plan[:2000],
    }


def _default_score() -> dict:
    """Fallback score when LLM fails."""
    summary = "AI 评分暂不可用"
    return {
        "overall": 50,
        "background_match": 5,
        "skills_overlap": 15,
        "experience_relevance": 15,
        "seniority": 5,
        "language_requirement": 5,
        "company_score": 5,
        "salary_match": 5,
        "location_match": 5,
        "culture_workload_match": 5,
        "summary": summary,
        "keywords": [],
        "fit_bullets": [],
        "missing_skills": [],
        "gap_analysis": [],
        "improvement_plan": _derive_improvement_plan([], [], summary),
    }


def word_overlap_score(resume_text: str, job_desc: str) -> int:
    """Simple keyword overlap score (0-100), used only as tiebreaker."""
    if not job_desc:
        return 0
    resume_words = set(resume_text.lower().split())
    job_words = set(job_desc.lower().split())
    if not job_words:
        return 0
    overlap = len(resume_words & job_words)
    ratio = min(1.0, overlap / len(job_words))
    return int(ratio * 100)


def run_job_match_pipeline(
    resume_text: str,
    jobs: list[dict] | None = None,
) -> tuple[list[dict], int]:
    """Score a resume against each job, sort by overall score, return top matches.

    Args:
        resume_text: Full resume content for matching
        jobs:        List of job dicts (id, title, company, location, salary_range, description).
                     If None, uses MOCK_JOPS from the old pipeline.

    Returns:
        (matches list, total evaluated count)
    """
    resume_text = (resume_text or "").strip()
    if not resume_text:
        return [], 0

    if jobs is None:
        from src.api.routes.jobs_routes import MOCK_JOBS
        jobs = MOCK_JOBS

    if not jobs:
        return [], 0

    results = []
    for job in jobs:
        score = _score_resume_vs_job(resume_text, job)

        # Build the match result combining job info + scores + derived display fields
        jd_text = str(job.get("description") or "")[:4000]
        match = {
            "job_id": job.get("id", ""),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "salary_range": job.get("salary_range", ""),
            "description": jd_text,
            "jd_snapshot": jd_text,
            # Multi-dimension scores (from Tatha's model)
            "scores": score,
            # Legacy display fields (backward compatible with frontend)
            "reason": score.get("summary", ""),
            "matched_skills": score.get("keywords", []),
            "missing_skills": score.get("missing_skills", []),
            "fit_bullets": score.get("fit_bullets", []),
            "gap_analysis": score.get("gap_analysis", []),
            "improvement_plan": score.get("improvement_plan", ""),
        }
        results.append(match)

    # Sort by overall score descending
    results.sort(key=lambda m: m["scores"]["overall"], reverse=True)
    return results, len(results)
