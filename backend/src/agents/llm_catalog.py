"""
LLM 模型适配清单 (Model Catalog)

团队维护的 Looma 可用 LLM 模型目录，供「运维面 /v1/admin/llm-ops」展示，
并为 central_brain 的每次调用折算成本（审计）。
- 价格单位：¥ / 1M tokens（input, output）。本地 Ollama 模型 = 0。
- 价格为公开参考价（DeepSeek / OpenAI 官网），实际以供应商账单为准，团队可直接改此文件。
- default=True 表示该 provider 的默认 model（与 DEEPSEEK_MODEL / OPENAI_MODEL / OLLAMA_MODEL 对齐）。
- category 取值：chat（通用对话）/ reason（推理）/ code（代码）/ smart（高精度）/ vision（多模态）。

新增模型：往对应 provider 的列表加一条即可，运维面自动展示；
配合 env（DEEPSEEK_MODEL 等）与 LLM_PROVIDER_ORDER 即可启用为路由候选。
"""

LLM_MODEL_CATALOG: dict[str, list[dict]] = {
    "deepseek": [
        {
            "id": "deepseek-chat",
            "label": "DeepSeek-V3",
            "cost_in": 1.0,
            "cost_out": 2.0,
            "ctx_k": 64,
            "category": "chat",
            "default": True,
            "note": "通用对话 / 意图解析（默认）",
        },
        {
            "id": "deepseek-reasoner",
            "label": "DeepSeek-R1",
            "cost_in": 4.0,
            "cost_out": 16.0,
            "ctx_k": 64,
            "category": "reason",
            "default": False,
            "note": "复杂推理 / 报告生成（可选）",
        },
    ],
    "openai": [
        {
            "id": "gpt-3.5-turbo",
            "label": "GPT-3.5-Turbo",
            "cost_in": 0.5,
            "cost_out": 1.5,
            "ctx_k": 16,
            "category": "chat",
            "default": True,
            "note": "轻量对话（默认）",
        },
        {
            "id": "gpt-4o",
            "label": "GPT-4o",
            "cost_in": 18.0,
            "cost_out": 72.0,
            "ctx_k": 128,
            "category": "smart",
            "default": False,
            "note": "高精度任务（可选）",
        },
    ],
    "ollama": [
        {
            "id": "qwen2.5-coder:1.5b",
            "label": "Qwen2.5-Coder 1.5B",
            "cost_in": 0.0,
            "cost_out": 0.0,
            "ctx_k": 32,
            "category": "code",
            "default": True,
            "note": "本地免费 · 代码/轻任务（默认）",
        },
        {
            "id": "qwen2.5:7b",
            "label": "Qwen2.5 7B",
            "cost_in": 0.0,
            "cost_out": 0.0,
            "ctx_k": 32,
            "category": "chat",
            "default": False,
            "note": "本地免费 · 通用（可选）",
        },
        {
            "id": "llama3.1:8b",
            "label": "Llama 3.1 8B",
            "cost_in": 0.0,
            "cost_out": 0.0,
            "ctx_k": 128,
            "category": "chat",
            "default": False,
            "note": "本地免费 · 多语言（可选）",
        },
    ],
}


def get_model_price(provider: str, model_id: str) -> tuple[float, float]:
    """返回 (cost_in, cost_out) ¥/1M tokens；未知模型返回 (0.0, 0.0)。"""
    for m in LLM_MODEL_CATALOG.get(provider, []):
        if m["id"] == model_id:
            return float(m["cost_in"]), float(m["cost_out"])
    return (0.0, 0.0)


def estimate_cost_yuan(provider: str, model_id: str, tokens_in: int, tokens_out: int) -> float:
    """按目录价格折算单次调用成本（元）。"""
    cost_in, cost_out = get_model_price(provider, model_id)
    return round((max(tokens_in, 0) * cost_in + max(tokens_out, 0) * cost_out) / 1_000_000, 6)


def catalog_for_provider(provider: str) -> list[dict]:
    """返回某 provider 的模型清单副本（供运维面渲染，避免外部修改目录）。"""
    return list(LLM_MODEL_CATALOG.get(provider, []))
