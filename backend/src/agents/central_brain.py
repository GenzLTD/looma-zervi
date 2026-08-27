"""
Central Brain — Intent parsing + dispatch to internal capability ports.

Migrated from old central_brain.py (518 lines), adapted for Flask.
Design: rules-first (fast & reliable for 1.5B models), LLM as enhancement fallback.
"""
from __future__ import annotations
from __future__ import annotations

import json
import random
import re
import time
import logging
from typing import Any

import requests
from flask import current_app

logger = logging.getLogger("looma.brain")

INTENTS = ("job_match", "resume_parse", "poetry", "credit", "mbti", "rag", "report", "greeting", "unknown")

# Keyword → intent rules (fallback when LLM unavailable)
# NOTE: Do NOT put 陪伴/安慰 in poetry — SaaS 六域 chips（情绪陪伴·压力疏导）会误入诗词兜底。
INTENT_KEYWORDS = {
    "poetry": [
        "诗词", "诗人", "古诗", "推荐一句", "思乡", "送别", "山水", "边塞", "励志",
        "一句诗", "唐诗", "宋词", "的诗", "的诗句", "诗句", "绝句", "律诗", "推荐诗",
    ],
    "job_match": ["匹配", "职位", "找工作", "有没有适合", "岗位", "求职", "招聘"],
    "resume_parse": ["上传", "解析简历", "分析简历", "提取简历"],
    "credit": ["征信", "信用", "验证"],
    "mbti": ["人格", "MBTI", "测评", "性格"],
    "report": ["报告", "日报", "周报", "月报", "生成报告"],
    "rag": [
        "知识库", "文档", "问一下", "查一下", "检索", "资料", "总结", "介绍", "介绍一下",
        "是什么", "什么是", "有哪些", "主要内容", "底座", "架构", "可以做什么", "能做什么",
        "有什么功能", "探索", "探索什么", "探索什么", "能探索", "星球", "星际探索",
        "六域", "职业域", "学习域", "生活域", "社交域", "健康域", "创意域",
        "情绪陪伴", "压力疏导", "时间管理", "效率提升", "职位匹配", "简历解析", "职业规划",
        "技能训练", "知识问答", "人格匹配", "组建舰队", "诗词推荐", "灵感激发",
        "planetx", "planetx 是什么", "planetx 能做什么", "planetx 有什么",
    ],
    "greeting": ["hi", "hello", "hey", "你好", "早上好", "晚上好", "您好", "很高兴", "再见", "谢谢", "感谢", "辛苦了", "在吗", "你是谁", "你能做什么", "帮我", "请问", "好的", "明白了", "ok", "thanks", "morning", "evening", "下午好", "晚安", "嗨"],
}

POETRY_RECOMMEND_THEMES = ("思乡", "送别", "山水", "边塞", "咏物", "励志", "田园", "怀古")

# SaaS Ask RAG modes: chat=multi-turn, deepseek=more retrieval+longer reasoning, fast=less retrieval+low temp
ASK_MODE_PRESETS: dict[str, dict[str, Any]] = {
    "chat": {
        "top_k": 3,
        "history_turns": 10,
        "temperature": 0.5,
        "max_tokens": 800,
        "reasoning": False,
    },
    "deepseek": {
        "top_k": 8,
        "history_turns": 4,
        "temperature": 0.55,
        "max_tokens": 2000,
        "reasoning": True,
    },
    "fast": {
        "top_k": 1,
        "history_turns": 0,
        "temperature": 0.1,
        "max_tokens": 280,
        "reasoning": False,
    },
}


def resolve_ask_mode(mode: str | None) -> str:
    m = (mode or "chat").strip().lower()
    return m if m in ASK_MODE_PRESETS else "chat"


def get_ask_mode_preset(mode: str | None) -> dict[str, Any]:
    return ASK_MODE_PRESETS[resolve_ask_mode(mode)]


def _format_session_history(session_history: list | None, turns: int) -> str:
    """Format recent chat turns for prompt injection (user/assistant pairs)."""
    if not session_history or turns <= 0:
        return ""
    lines: list[str] = []
    for msg in session_history[-turns:]:
        if not isinstance(msg, dict):
            continue
        role = "用户" if msg.get("role") == "user" else "助手"
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}：{content[:400]}")
    if not lines:
        return ""
    return "[对话历史]\n" + "\n".join(lines) + "\n\n"


def _format_match_report_block(context: dict[str, Any] | None) -> str:
    """Optional match-report summary for Ask (not navigator)."""
    report = (context or {}).get("match_report")
    if not isinstance(report, dict) or not report:
        return ""
    lines = [
        "[当前匹配报告上下文]",
        "以下为用户已保存的匹配报告摘要（非全文简历）。回答涉及匹配/缺口/技能时优先依据本段；",
        "若问题与报告无关，可忽略。不要编造报告中未出现的岗位或分数。",
        f"报告标题：{report.get('title') or '（无标题）'}",
        f"报告ID：{report.get('report_id') or ''}",
    ]
    resume_summary = str(report.get("resume_summary") or "").strip()
    if resume_summary:
        lines.append(f"简历摘要：{resume_summary}")
    for i, item in enumerate(report.get("top_items") or [], 1):
        if not isinstance(item, dict):
            continue
        matched = "、".join(str(x) for x in (item.get("matched_skills") or [])[:8])
        missing = "、".join(str(x) for x in (item.get("missing_skills") or [])[:8])
        lines.append(
            f"{i}. {item.get('job_title') or '职位'} · 综合分 {item.get('overall_score') or 0}"
            f" · 已匹配[{matched or '—'}] · 缺口[{missing or '—'}]"
            f" · 差距：{item.get('gap_analysis') or '—'}"
        )
    return "\n".join(lines) + "\n\n"


def _poetry_is_recommendation_query(text: str) -> bool:
    """Check if query is a short 'recommend a poem' type (no poem content)."""
    if not (text and text.strip()) or len(text.strip()) > 80:
        return False
    t = text.strip()
    return bool(re.search(r"推荐|来一句|来首|随便.*诗|一句诗", t))


def _call_llm(
    prompt: str,
    *,
    temperature: float = 0.3,
    max_tokens: int | None = None,
) -> str | None:
    """Call the configured LLM provider via DeepSeek/OpenAI API.
    Returns response text or None on failure."""
    config = current_app.config
    provider_order = [p.strip().lower() for p in config.get("LLM_PROVIDER_ORDER", "deepseek").split(",")]

    for provider in provider_order:
        try:
            if provider == "deepseek":
                api_key = (config.get("DEEPSEEK_API_KEY") or "").strip()
                if not api_key or api_key.lower() in ("skip", "your-deepseek-api-key"):
                    continue
                url = f"{config['DEEPSEEK_BASE_URL']}/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload: dict[str, Any] = {
                    "model": config["DEEPSEEK_MODEL"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    payload["max_tokens"] = max_tokens
                resp = requests.post(url, json=payload, headers=headers, timeout=float(config.get("API_REQUEST_TIMEOUT", 90)))
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            elif provider == "openai":
                openai_key = (config.get("OPENAI_API_KEY") or "").strip()
                if not openai_key or openai_key.lower() in ("skip", "your-openai-api-key"):
                    continue
                url = f"{config.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')}/chat/completions"
                headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
                payload = {
                    "model": config.get("OPENAI_MODEL", "gpt-3.5-turbo"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    payload["max_tokens"] = max_tokens
                resp = requests.post(url, json=payload, headers=headers, timeout=float(config.get("API_REQUEST_TIMEOUT", 90)))
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            elif provider == "ollama":
                host = config.get("OLLAMA_HOST", "http://127.0.0.1:11434")
                url = f"{host.rstrip('/')}/api/generate"
                model = config.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
                options: dict[str, Any] = {"temperature": temperature}
                if max_tokens is not None:
                    options["num_predict"] = max_tokens
                payload = {"model": model, "prompt": prompt, "stream": False, "options": options}
                resp = requests.post(url, json=payload, timeout=float(config.get("API_REQUEST_TIMEOUT", 90)))
                resp.raise_for_status()
                return resp.json().get("response", "")

        except Exception as e:
            logger.warning(f"LLM provider {provider} failed: {e}")
            continue

    logger.error("All LLM providers unavailable")
    return None


def _parse_intent_llm(message: str) -> tuple[str, float, dict[str, Any]] | None:
    """Use LLM to parse intent. Returns (intent, confidence, slots) or None."""
    try:
        system = (
            "你是一个意图分类器。根据用户输入，输出且仅输出一个 JSON 对象，不要其他文字。"
            "JSON 必须包含：\"intent\"（取值仅限: job_match, resume_parse, poetry, credit, mbti, rag, report, unknown），"
            "\"confidence\"（0 到 1 的浮点数），可选 \"slots\"（对象）。"
            "\n分类规则："
            "\n- rag: 问知识/文档/概念/系统是什么、平台介绍、功能说明、总结/介绍/检索、可以做什么、探索什么、六域相关"
            "\n- poetry: 涉及诗词/诗人/古诗/唐诗宋词"
            "\n- job_match: 求职/职位匹配/找工作"
            "\n- resume_parse: 上传或解析简历"
            "\n- credit: 征信/信用验证"
            "\n- mbti: 人格测评/MBTI/性格分析"
            "\n- report: 生成日报/周报/月报"
            "\n- unknown: 以上都不匹配"
        )
        response = _call_llm(f"{system}\n\n用户输入：{message.strip()}\n\n请输出 JSON：")
        if not response:
            return None

        text = response.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if m:
                text = m.group(1).strip()
        data = json.loads(text)
        intent = (data.get("intent") or "unknown").lower()
        if intent not in INTENTS:
            intent = "unknown"
        confidence = float(data.get("confidence", 0.5))
        slots = data.get("slots") if isinstance(data.get("slots"), dict) else {}
        return (intent, confidence, slots)
    except Exception:
        return None


def _parse_intent_rules(message: str) -> str:
    """Rules-based intent parsing (fast, reliable fallback)."""
    msg = (message or "").strip().lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            return intent
    return "unknown"


def parse_intent(message: str, navigator_mode: bool = False) -> tuple[str, float, dict[str, Any]]:
    """Parse user message → intent + confidence + slots.
    Strategy: rules first (reliable), LLM as enhancement."""
    if navigator_mode:
        return ("unknown", 0.5, {})

    rule_intent = _parse_intent_rules(message)
    if rule_intent != "unknown":
        return (rule_intent, 0.9, {})

    out = _parse_intent_llm(message)
    if out is not None:
        intent, confidence, slots = out
        if intent != "unknown" and confidence >= 0.7:
            return (intent, confidence, slots)

    return ("unknown", 0.3, {})


def dispatch(
    intent: str,
    query: str,
    context: dict[str, Any] | None = None,
    slots: dict[str, Any] | None = None,
    resume_text: str | None = None,
    _timing: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Dispatch intent → internal capability port, return result dict."""
    slots = slots or {}
    context = context or {}
    text = query.strip() or slots.get("text") or slots.get("content") or ""
    _timing = _timing or {}

    # ── RAG 问答 ──
    if intent == "rag":
        try:
            from src.rag.chroma_client import search_chroma
            preset = get_ask_mode_preset(context.get("ask_mode"))
            top_k = int(preset["top_k"])
            history_turns = int(preset["history_turns"])
            temperature = float(preset["temperature"])
            max_tokens = int(preset["max_tokens"])
            reasoning = bool(preset["reasoning"])

            t_retrieve = time.time()
            results = search_chroma(query, n_results=top_k)
            _timing["rag_retrieve"] = int((time.time() - t_retrieve) * 1000)

            history_block = _format_session_history(
                context.get("session_history"), history_turns
            )
            report_block = _format_match_report_block(context)
            style = (
                "请分步骤深入推理与分析，给出较完整、有层次的回答；必要时先列要点再展开。"
                if reasoning
                else (
                    "请用两三句话直接回答，不要展开背景，不要列长清单。"
                    if top_k <= 1
                    else "回答要友好、简洁，结合上下文自然延续对话。"
                )
            )

            if results:
                # Use retrieved context as the primary source. The LLM is told it may
                # still fall back on general knowledge when the context is incomplete.
                context_text = "\n\n".join(r.get("content", "") for r in results)
                prompt = (
                    "你是 PlanetX 星际导航员，一位热情、简洁的 AI 助手。"
                    "请根据以下参考资料回答用户问题，并自然地介绍 PlanetX 的六域探索体系。"
                    "如果参考资料不够完整，可以结合通用知识补充，但不要强调「资料没有提到」或「这一解释并非来自参考资料」。"
                    "用第一人称「我」或「我们」回答，营造陪伴感。\n"
                    f"{style}\n\n"
                    f"{history_block}"
                    f"{report_block}"
                    f"参考资料：\n{context_text}\n\n"
                    f"用户问题：{query}\n\n"
                    f"回答："
                )
            else:
                # Fallback: no documents in the knowledge base, answer from general knowledge
                # with a natural promotion of PlanetX six domains.
                prompt = (
                    "你是 PlanetX 星际导航员，一位热情、简洁的 AI 助手。"
                    "请用友好、有吸引力的方式回答用户，并自然地介绍 PlanetX 的六域探索体系："
                    "职业域、学习域、生活域、社交域、健康域、创意域。"
                    "如果用户的问题与这些域相关，请邀请他们进一步体验对应功能。\n"
                    f"{style}\n\n"
                    f"{history_block}"
                    f"{report_block}"
                    f"用户问题：{query}\n\n"
                    f"回答："
                )
            t_llm = time.time()
            answer = _call_llm(
                prompt, temperature=temperature, max_tokens=max_tokens
            ) or "知识库检索失败，请稍后再试"
            _timing["rag_llm"] = int((time.time() - t_llm) * 1000)

            sources = [{"chunk_text": r.get("content", "")[:200], "score": r.get("score")} for r in results]
            return {
                "answer": answer,
                "_sources": sources,
                "slots": slots,
                "ask_mode": resolve_ask_mode(context.get("ask_mode")),
            }
        except Exception as e:
            logger.error(f"RAG query failed: {e}", exc_info=True)
            return {"message": f"RAG 查询失败: {str(e)}", "answer": "", "slots": slots}

    # ── 职位匹配 ──
    if intent == "job_match":
        rtext = (resume_text or "").strip() or (context.get("resume_text") or "") or (slots.get("resume_text") or "")
        if not rtext:
            return {"message": "请先提供简历内容", "status": "pending",
                    "hint": "可通过上传简历或传入 resume_text", "slots": slots,
                    "answer": "请先提供你的简历内容或工作经历描述，我来帮你匹配适合的职位。"}
        try:
            from src.pipeline.job_match_pipeline import run_job_match_pipeline
            results_list, total = run_job_match_pipeline(resume_text=rtext)
            if results_list:
                lines = ["根据你的简历，推荐以下匹配职位：\n"]
                for i, m in enumerate(results_list[:5], 1):
                    lines.append(f"{i}. {m.get('title', m.get('job_title', '-'))} — 匹配度 {m.get('score', '-')}")
                lines.append(f"\n共评估 {total} 个职位。要了解更多细节或针对性建议，随时问我！")
                answer = "\n".join(lines)
            else:
                answer = "已分析你的简历，暂未找到高匹配职位。试试补充更多技能或工作经历？"
            return {"message": "已根据简历完成职位匹配", "answer": answer, "matches": results_list, "total_evaluated": total, "slots": slots}
        except Exception as e:
            return {"message": "职位匹配失败", "error": str(e), "answer": "职位匹配暂时不可用，请稍后重试。", "slots": slots}

    # ── 简历解析 ──
    if intent == "resume_parse":
        # Guard: if text looks like a search query rather than resume content,
        # fall through to RAG instead of trying to parse it as a resume.
        search_indicators = ["查找", "搜索", "帮我找", "帮我查", "有没有", "在哪里", "是谁", "介绍", "了解"]
        if text and any(ind in text for ind in search_indicators) and len(text) < 200:
            # Redirect to RAG with a helpful note
            rag_prompt = (
                "用户似乎在查找或了解某个人，而不是上传简历进行解析。"
                "请根据你的知识尽可能回答用户的问题。"
                "如果你无法获取该人物的实时信息，请诚实说明，并建议用户通过正规渠道核实。\n\n"
                f"用户问题：{query}\n\n"
                f"回答："
            )
            answer = _call_llm(rag_prompt) or "我暂时无法获取该人物的详细信息，建议通过 LinkedIn 或相关学校/公司官网核实。"
            return {"answer": answer, "intent_redirected": "rag", "slots": slots}

        if text:
            try:
                from src.agents.document_agents import run_document_analysis
                extracted = run_document_analysis("resume", text)
                skills = extracted.get("skills", []) if isinstance(extracted, dict) else []
                skill_str = "、".join(skills[:8]) if skills else "未识别出明确技能"
                answer = f"已解析你的简历。\n\n识别技能：{skill_str}\n\n需要我帮你匹配职位或分析职业方向吗？"
                return {"message": "已解析简历", "answer": answer, "extracted": extracted, "slots": slots}
            except Exception as e:
                return {"message": "简历解析失败", "error": str(e), "answer": "简历解析暂时不可用，请稍后重试。", "slots": slots}
        return {"message": "请提供简历文本内容", "status": "pending", "slots": slots,
                "answer": "请提供简历文本内容，我来帮你解析技能并推荐职位。"}

    # ── 诗词推荐 ──
    if intent == "poetry":
        if text:
            try:
                from src.agents.poetry_search import search_poems
                search_query = text
                if _poetry_is_recommendation_query(text):
                    theme = random.choice(POETRY_RECOMMEND_THEMES)
                    search_query = theme

                poetry_k = int(get_ask_mode_preset(context.get("ask_mode"))["top_k"])
                poems = search_poems(search_query, n_results=poetry_k)
                if poems:
                    context_text = "\n\n".join(
                        f"【{p.get('dynasty', '')}】{p.get('title', '')} — {p.get('author', '')}\n{p.get('content', '')}"
                        for p in poems
                    )
                    prompt = (
                        f"从以下诗词中挑选最合适的一首推荐给用户。用户查询：{text}\n\n"
                        f"候选诗词：\n{context_text}\n\n"
                        f"请以 JSON 格式返回：title、author、dynasty、content（选最有代表性的两句）、theme。只输出 JSON。"
                    )
                    response = _call_llm(prompt)
                    if response:
                        resp_text = response.strip()
                        if "```" in resp_text:
                            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp_text)
                            if m:
                                resp_text = m.group(1).strip()
                        try:
                            extracted = json.loads(resp_text)
                            if isinstance(extracted.get("content"), list):
                                extracted["content"] = "\n".join(extracted["content"])
                            answer = f"{extracted.get('title', '')} · {extracted.get('author', '')}（{extracted.get('dynasty', '')}）\n\n{extracted.get('content', '')}\n\n{extracted.get('theme', '')}".strip()
                            return {"message": "已为您推荐诗词", "answer": answer, "extracted": extracted, "slots": slots}
                        except json.JSONDecodeError:
                            pass

                    # LLM failed, return first poem from search
                    best = poems[0]
                    extracted = {
                        "title": best.get("title", ""), "author": best.get("author", ""),
                        "dynasty": best.get("dynasty", ""),
                        "content": (best.get("content", "") or "")[:100],
                        "theme": search_query,
                    }
                    answer = f"{extracted['title']} · {extracted['author']}（{extracted['dynasty']}）\n\n{extracted['content']}".strip()
                    return {
                        "answer": answer,
                        "extracted": extracted,
                        "slots": slots,
                    }
                return {"message": "未找到匹配的诗词", "status": "pending", "slots": slots,
                        "answer": "这个方向还没找到合适诗句，换个心情或主题试试？"}
            except Exception as e:
                return {"message": "诗词检索失败", "error": str(e), "slots": slots,
                        "answer": "诗词库暂时无法访问，请稍后再试。"}
        return {"message": "诗人/诗词推荐已就绪", "status": "pending", "slots": slots,
                "answer": "想找什么主题的诗句？心情、季节、场景都行，告诉我就好。"}

    # ── MBTI 测评 ──
    if intent == "mbti":
        from src.agents.mbti_analyzer import MBTITextAnalyzer, MIN_TEXT_LENGTH
        from src.agents.mbti_career_match import get_career_match
        if text and len(text.strip()) >= MIN_TEXT_LENGTH:
            try:
                analyzer = MBTITextAnalyzer()
                analysis = analyzer.analyze_text(text)
                if analysis.get("mbti_type") and analysis["mbti_type"] != "XXXX":
                    career = get_career_match(analysis["mbti_type"])
                    mbti = analysis["mbti_type"]
                    traits = analysis.get("traits", {})
                    career_tip = career.get("suggestion", "") if isinstance(career, dict) else ""
                    answer = (
                        f"分析完成！你的 MBTI 类型可能是 **{mbti}**。\n\n"
                        f"值得关注的职业方向：{career_tip}\n\n"
                        f"心理学笔记已记录，有新的自我觉察随时来找我聊！"
                    )
                    return {"answer": answer, "extracted": {**analysis, "career_match": career}, "slots": slots}
                answer = "看起来信息还不够判断你的性格类型，再和我多聊几句？比如你面对压力时的反应、更喜欢独立还是协作。"
                return {"answer": answer, "extracted": analysis, "slots": slots}
            except Exception as e:
                return {"message": "人格测评分析失败", "error": str(e), "answer": "性格分析暂时不可用，请稍后重试。", "slots": slots}
        return {"message": "请描述您的做事风格（至少20字）", "status": "pending", "slots": slots,
                "answer": "想了解你的性格类型？来和我说说你的做事风格、人际偏好，我会帮你分析。"}

    # ── 报告生成 ──
    if intent == "report":
        try:
            from src.pipeline.report_gen import ReportGenerator
            reporter = ReportGenerator()
            report_type = "daily"
            if "周" in query or "weekly" in query.lower():
                report_type = "weekly"
            elif "月" in query or "monthly" in query.lower():
                report_type = "monthly"
            path = reporter.generate_report(report_type)
            type_cn = {"daily": "日报", "weekly": "周报", "monthly": "月报"}.get(report_type, report_type)
            return {"message": f"已生成{type_cn}报告", "answer": f"{type_cn}已生成，请查看。", "path": str(path), "slots": slots}
        except Exception as e:
            return {"message": "报告生成失败", "error": str(e), "answer": "报告生成暂时不可用，请稍后重试。", "slots": slots}

    # ── Navigator 对话模式 ──
    if context.get("navigator_mode") and intent == "unknown":
        try:
            user_id = context.get("user_id", "guest")
            session_id = context.get("session_id", "")
            session_history = context.get("session_history", [])
            current_stage = context.get("current_stage", "greeting")
            active_domain = context.get("active_domain", "")
            session_num = context.get("session_num", 1)
            interaction_count = context.get("interaction_count", 0)

            # ── Engine initialization ──
            db = current_app._db if hasattr(current_app, '_db') else None
            from src.agents.domain_engine import get_domain_engine
            from src.agents.navigator_memory import get_navigator_memory
            from src.agents.convergence import get_convergence

            engine = get_domain_engine(db=db)
            memory = get_navigator_memory(db=db)
            convergence = get_convergence(engine=engine, memory=memory)

            # ── Stage: domain_enter → record domain entry + cross-domain effects ──
            domain_context: dict = {}
            if current_stage == "domain_enter" and active_domain:
                crossing = engine.record_domain_enter(user_id, session_id, active_domain)
                if crossing:
                    domain_context = crossing

            # ── Stage: choice_made → record choice + imprint ──
            if current_stage == "choice_made" and active_domain:
                user_choice = context.get("last_choice", "")
                if user_choice:
                    engine.record_choice(session_id, active_domain, user_choice, user_id)
                    importance = context.get("choice_importance", 1.0)
                    memory.record_choice(user_id, active_domain, user_choice,
                                         importance=importance, session_id=session_id)

            # ── Intelligence: detect emergent strategies ──
            strategies = engine.detect_strategies(user_id)
            if strategies and db:
                for s in strategies:
                    try:
                        db.log_emergent_strategy(user_id, s["strategy"])
                    except Exception:
                        pass

            # ── Check convergence trigger ──
            if convergence.should_trigger_convergence(user_id, session_id, interaction_count):
                current_stage = "convergence"
                convergence.mark_convergence_triggered(session_id)
                logger.info(f"Convergence triggered: user={user_id} session={session_id}")

            # ── Build Navigator system prompt (core of the engine) ──
            navigator_system = convergence.build_system_prompt(
                user_id=user_id,
                session_id=session_id,
                active_domain=active_domain or None,
                confidence=context.get("confidence", 0.5),
                stage=current_stage,
                query=query,
                session_num=session_num,
            )

            # ── Psychology layer (optional enhancement) ──
            psychology_hint = ""
            if current_app.config.get("PSYCHOLOGY_ENABLED", True):
                try:
                    from src.agents.psychology_analyzer import analyze_conversation, build_psychology_hint
                    psychology_result = analyze_conversation(query, session_history, active_domain)
                    psychology_hint = build_psychology_hint(psychology_result)
                except Exception:
                    pass

            # ── Build chat history ──
            history_text = ""
            for msg in (session_history or [])[-4:]:
                role = "用户" if msg.get("role") == "user" else "Navigator"
                content = msg.get("content", "")[:80]
                history_text += f"{role}：{content}\n"

            # ── Assemble full prompt ──
            domain_hint = f"[当前域：{active_domain}]\n" if active_domain else ""

            # Inject domain crossing narrative if available
            crossing_narrative = ""
            if domain_context.get("crossing_narrative"):
                crossing_narrative = f"\n[跨域感知 — 注入你的回应中]\n{domain_context['crossing_narrative']}\n"

            # Inject echo narrative if active
            echo_narrative = ""
            if domain_context.get("echo") and domain_context["echo"].get("narrative_hint"):
                echo_narrative = f"\n[回声感知 — 你感知到跨域共鸣]\n{domain_context['echo']['narrative_hint']}\n"

            full_prompt = (
                f"{navigator_system}\n\n"
                f"{domain_hint}"
                f"{psychology_hint}\n"
                f"{crossing_narrative}"
                f"{echo_narrative}"
                f"[对话历史]\n{history_text}\n"
                f"[用户消息] {query}\n\n"
                f"请以 Navigator 身份回应（不超过120字，纯文本）："
            )

            t_nav = time.time()
            answer = _call_llm(full_prompt) or "...（信号中断）"
            _timing["navigator_llm"] = int((time.time() - t_nav) * 1000)

            # Build engine metadata for response
            engine_ctx = engine.build_navigator_context(user_id, session_id)
            navigator_extras: dict = {
                "navigator_mode": True,
                "current_stage": current_stage,
                "active_domain": active_domain,
                "estimated_act": engine_ctx.get("estimated_act"),
                "imprint": engine_ctx.get("imprint"),
                "echo_chain": engine_ctx.get("echo_chain_length", 0),
                "convergence_triggered": current_stage == "convergence",
                "active_strategies": engine_ctx.get("active_strategies", []),
                "domain_context": domain_context,
            }
            # Remove null-ish values
            navigator_extras = {k: v for k, v in navigator_extras.items() if v not in (None, "", [], {})}

            return {
                "answer": answer.strip(),
                "extracted": navigator_extras,
                "slots": slots,
            }
        except Exception as e:
            logger.error(f"Navigator failed: {e}", exc_info=True)
            return {"answer": "...（信号中断）", "slots": slots}

    # ── Greeting ──
    if intent == "greeting":
        welcome = "\n".join([
            "你好，探索者！我是 PlanetX 星际导航员。",
            "",
            "PlanetX 有六大探索域等你开启：",
            "🌍 职业域 — 职位匹配 · 简历解析 · 职业规划",
            "📚 学习域 — 技能训练 · 知识问答 · AI 辅导",
            "🏡 生活域 — 时间管理 · 效率提升",
            "👥 社交域 — 人格匹配 · 组建舰队",
            "💚 健康域 — 情绪陪伴 · 压力疏导",
            "🎨 创意域 — 诗词推荐 · 灵感激发",
            "",
            "想从哪个开始探索？",
        ])
        return {"answer": welcome, "slots": slots}

    # ── Unknown ──
    # Fallback to general LLM chat so trivial / ambiguous inputs are not met with a dead-end.
    try:
        preset = get_ask_mode_preset(context.get("ask_mode"))
        history_block = _format_session_history(
            context.get("session_history"), int(preset["history_turns"])
        )
        report_block = _format_match_report_block(context)
        style = (
            "请分步骤深入分析后再回答。"
            if preset["reasoning"]
            else (
                "请用一两句话直接回应。"
                if int(preset["top_k"]) <= 1
                else "回答简洁友好，可结合对话历史延续话题。"
            )
        )
        prompt = (
            "你是 PlanetX 星际导航员，一位热情、简洁的 AI 助手。"
            "请自然、友好地回应用户的话。"
            "如果用户的话含义不太明确，请主动介绍 PlanetX 的六域探索体系："
            "职业域、学习域、生活域、社交域、健康域、创意域，并邀请用户选择一个方向继续探索。"
            "语气要有陪伴感，让用户感受到这是一个可以长期成长的地方。\n"
            f"{style}\n\n"
            f"{history_block}"
            f"{report_block}"
            f"用户：{query}\n\n"
            "回答："
        )
        answer = _call_llm(
            prompt,
            temperature=float(preset["temperature"]),
            max_tokens=int(preset["max_tokens"]),
        )
        if not answer:
            # Do not masquerade as a successful navigator greeting when all providers fail
            # (common overseas cause: DeepSeek 402 Payment Required / empty balance).
            answer = (
                "星际导航暂时连不上 AI 服务（常见原因：DeepSeek 配额不足或密钥失效）。"
                "请稍后重试，或联系客服 zervi@genz.ltd。"
            )
    except Exception as e:
        logger.warning(f"Unknown fallback LLM failed: {e}")
        answer = (
            "星际导航暂时连不上 AI 服务（常见原因：DeepSeek 配额不足或密钥失效）。"
            "请稍后重试，或联系客服 zervi@genz.ltd。"
        )
    return {"answer": answer, "slots": slots, "ask_mode": resolve_ask_mode(context.get("ask_mode"))}
