"""
Document Agents — Resume / Job / Credit / Document analysis via LLM.
Migrated from old document_agents.py, adapted for Flask.
"""
from __future__ import annotations
import json
import logging
import re

logger = logging.getLogger("looma.doc_agents")


class DocumentAnalysisError(Exception):
    """Structured failure from document LLM extraction."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _extract_json_object(text: str) -> dict | None:
    """Parse a JSON object from raw LLM output (fences / prose wrapper OK)."""
    if not text:
        return None
    resp = text.strip()
    if "```" in resp:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp)
        if m:
            resp = m.group(1).strip()
    try:
        data = json.loads(resp)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    start = resp.find("{")
    end = resp.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(resp[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def run_document_analysis(doc_type: str, text: str) -> dict | None:
    """Analyze a document (resume, job, credit report etc.) via LLM.

    Returns structured dict, or None on soft failure.
    Raises DocumentAnalysisError when the cause should be surfaced to the client
    (e.g. all LLM providers unavailable / JSON parse failed after a model reply).
    """
    prompts = {
        "resume": (
            "你是结构化数据提取器，不是聊天助手，禁止自我介绍。\n"
            "从以下简历文本中提取信息，只输出一个 JSON 对象，不要 Markdown，不要解释。\n"
            "字段必须使用以下键名：\n"
            "{\n"
            '  "name": "...",\n'
            '  "email": "...",\n'
            '  "phone": "...",\n'
            '  "summary": "...",\n'
            '  "skills": ["..."],\n'
            '  "experiences": [{"company":"...","title":"...","start_date":"...","end_date":"...","description":"..."}],\n'
            '  "education": [{"school":"...","degree":"...","field":"...","start_date":"...","end_date":"..."}],\n'
            '  "projects": [{"name":"...","description":"..."}],\n'
            '  "languages": ["..."],\n'
            '  "certifications": ["..."]\n'
            "}\n"
            "\n简历文本：\n{text}"
        ),
        "credit": (
            "你是一个征信分析专家。从以下信用报告文本中提取关键信息，输出 JSON 格式："
            "{\"credit_score\": \"...\", \"loan_history\": [], \"payment_status\": \"...\", "
            "\"risk_factors\": [], \"summary\": \"...\"}"
            "\n\n征信文本：\n{text}"
        ),
        "job": (
            "你是结构化数据提取器，不是聊天助手，禁止自我介绍。\n"
            "从以下职位描述文本中提取信息，只输出一个 JSON 对象，不要 Markdown，不要解释。\n"
            "{\n"
            '  "title": "职位名称（必须提取）",\n'
            '  "company": "公司名称",\n'
            '  "location": "工作地点（城市/远程）",\n'
            '  "salary_range": "薪资范围",\n'
            '  "description": "职位描述摘要（200字以内）",\n'
            '  "requirements": ["要求1", "要求2"],\n'
            '  "responsibilities": ["职责1", "职责2"],\n'
            '  "tags": ["标签1", "标签2"],\n'
            '  "seniority_level": "初级/中级/高级/专家",\n'
            '  "employment_type": "全职/兼职/实习/外包",\n'
            '  "remote_policy": "远程/混合/现场",\n'
            '  "source": "upload"\n'
            "}\n\n"
            "职位描述文本：\n{text}"
        ),
    }

    prompt_template = prompts.get(doc_type)
    if not prompt_template:
        logger.warning(f"Unknown doc_type: {doc_type}")
        return None

    # Do not use str.format — prompt templates embed JSON braces like {"name": ...}
    prompt = prompt_template.replace("{text}", text[:4000], 1)

    try:
        from src.agents.central_brain import _call_llm

        response = _call_llm(prompt, temperature=0.1, max_tokens=2048)
        if not response:
            raise DocumentAnalysisError(
                "llm_unavailable",
                "AI 服务暂不可用（模型未配置、欠费或上游失败）。"
                "请检查 DeepSeek/OpenAI 配额与密钥，稍后重试。",
            )

        data = _extract_json_object(response)
        if not data:
            logger.error(
                "Document analysis JSON parse failed for %s, resp_prefix=%r",
                doc_type,
                (response or "")[:240],
            )
            raise DocumentAnalysisError(
                "parse_failed",
                "AI 返回了内容但未能解析为有效 JSON。"
                "请重试，或改用粘贴文本。",
            )
        return data
    except DocumentAnalysisError:
        raise
    except Exception as e:
        logger.error(f"Document analysis failed for {doc_type}: {e}")
        return None
