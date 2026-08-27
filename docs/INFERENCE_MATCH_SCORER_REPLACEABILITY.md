# 推理与匹配打分可替换性 · 接口与里程碑

> **版本：** 0.1 · **日期：** 2026-07-23  
> **状态：** 草案 — 供审计 / 评审；**不触发线上切流**  
> **性质：** 工程 ADR + 可验收里程碑（卡脖子应对：第三方 LLM API → 可替换推理与垂域精排）  
> **关联：** [MANIFESTO.md](./MANIFESTO.md) §4.3–4.4 · [TRUST_LAYER.md](./TRUST_LAYER.md) §6 · [CURRENT_SYSTEM_ARCHITECTURE.md](./CURRENT_SYSTEM_ARCHITECTURE.md)  
> **真源代码（现状）：** `backend/src/agents/central_brain.py`（`_call_llm`）· `backend/src/pipeline/job_match_pipeline.py`（`_score_resume_vs_job` / `run_job_match_pipeline`）

---

## 0. 一句话

> **产品契约（match 分数 schema、对外 API）不变；推理与职位打分必须可插拔。**  
> 解卡脖子优先顺序：换供应商 / 私有部署 → 无 LLM 仍可排序 → 标注闭环 → 垂域精排自研。  
> **不做**从零训练通用大模型。

---

## 1. 问题陈述（可审计）

| # | 现状事实 | 风险 |
|---|----------|------|
| R1 | 对话、意图、简历分析、职位匹配等统一经 `_call_llm` 调 DeepSeek / OpenAI / Ollama HTTP API | 密钥、计费、合规、断服导致能力整体不可用 |
| R2 | `job_match_pipeline._score_resume_vs_job` 将 **排序真值** 与 **自然语言解释** 绑在同一次 LLM JSON 调用 | API 不可用时仅能回落 `_default_score()`（全员≈50），列表失去区分度 |
| R3 | 纲领已写 Trust v2「可训练模型」、`game_routes` 注释「replaceable by trained model later」，但 **无统一 Scorer / Inference 端口与里程碑** | 自研路径不可审计、不可验收 |
| R4 | 前端 / MCP / 配额依赖既有 match 字段（`scores.*`、`gap_analysis` 等） | 换模型若改 schema 会造成多端回归 |

**本文件裁定的目标：** 在不破坏 R4 契约的前提下，消除 R1–R3 的不可替换性。

---

## 2. 非目标（刻意不做）

| 非目标 | 原因 |
|--------|------|
| 自训通用 Chat / 基座大模型 | 投入与产品壁垒不匹配 |
| 改变 `/v1/jobs/match` 对外分数 schema（11 维 + gap 等） | 多端与报告契约已绑定 |
| 用户可见「信任分 / 信用分」由模型直接输出 | 与 [MANIFESTO](./MANIFESTO.md) / [TRUST_LAYER](./TRUST_LAYER.md) 一致 |
| M0–M1 将 PyTorch 训练栈打进主服务进程 | 训练离线；在线只加载推理或规则 |
| 本阶段强制下线云端 LLM | 云端可作解释与兜底；排序须可离线 |

---

## 3. 设计原则

1. **两层端口，不混职责**  
   - **L1 InferencePort**：任意文本补全（chat / JSON extract）  
   - **L2 JobMatchScorer**：简历×职位 → 结构化分数（须过 `_sanitize_scores`）
2. **数字分 vs 解释文案可分离**  
   - 排序依赖 Scorer；`summary` / `fit_bullets` / `gap_analysis` / `improvement_plan` 可走 Inference，也可为空。
3. **统一钳制**  
   - 任何 Scorer 输出必须经现有 `_sanitize_scores`（或等价函数），保证字段范围可审计。
4. **配置切流，默认不改生产行为**  
   - 未设新 env 时行为 = 今日 `llm_v1`（现 prompt + `_call_llm`）。
5. **可观测**  
   - 每次打分记录 `scorer`、`provider`、`model`（日志或表），便于对照与审计。

---

## 4. 接口契约（拟议；实现以代码 PR 为准）

### 4.1 L1 — InferencePort

**拟议路径：** `backend/src/inference/ports.py` + `providers/{openai,deepseek,ollama}.py`

```text
InferenceRequest
  task: str              # "chat" | "json_extract" | "intent" | ...
  prompt: str
  temperature: float = 0.3
  max_tokens: optional int

InferenceResult
  text: optional str
  provider: str          # openai | deepseek | ollama | offline
  model: str
  latency_ms: int

InferencePort.complete(req) -> InferenceResult
```

**兼容策略：**

- 保留 `central_brain._call_llm(prompt) -> str | None` 为薄包装，委托 `get_inference().complete(...).text`。  
- 调用点（简历、MBTI、RAG、征信、MCP 等）**M0 可不改签名**。  
- 配置继续使用 `LLM_PROVIDER_ORDER`；允许 OpenAI-compatible 自建端点（vLLM 等）挂在 `OPENAI_BASE_URL`。

### 4.2 L2 — JobMatchScorer

**拟议路径：** `backend/src/matching/ports.py` + `scorers/{llm_v1,heuristic_v0,ranker_v1}.py`

```text
MatchPair
  resume_text: str
  job: dict              # id, title, company, location, salary_range, description

JobMatchScorer
  name() -> str          # "llm_v1" | "heuristic_v0" | "ranker_v1"
  score(pair) -> dict    # 原始分数字典；pipeline 内必须 _sanitize_scores
```

**`run_job_match_pipeline` 目标形态：**

```text
for job in jobs:
  raw = get_job_match_scorer().score(MatchPair(resume_text, job))
  scores = _sanitize_scores(raw)
  # 组装现有 match 响应字段（reason / matched_skills / gap_* 等）不变
```

**配置（拟议 env）：**

| 变量 | 默认 | 含义 |
|------|------|------|
| `JOB_MATCH_SCORER` | `llm_v1` | 主打分后端 |
| `JOB_MATCH_EXPLAIN` | `llm` | `llm` = 解释走 Inference；`none` = 解释字段允许空 |
| `JOB_MATCH_FALLBACK` | `heuristic_v0` | 主 Scorer 失败时的排序兜底 |

### 4.3 对外契约冻结（审计红线）

以下字段语义与取值范围 **不得在 M0–M3 无 RFC 变更**：

- `scores.overall`（0–100）及既有 11 维数值字段  
- `keywords` / `fit_bullets` / `missing_skills` / `gap_analysis` / `improvement_plan`  
- 路由：`POST` 职位匹配（含 consent `job_match`、配额）  
- 报告版本常量：`PIPELINE_VERSION`（变更须显式 bump 并写修订记录）

允许新增 **非破坏** 元数据（如响应或日志中的 `scorer`、`provider`），须在 PR 说明「additive only」。

### 4.4 后续同构端口（本文件登记，不阻塞 M0–M3）

| 端口 | 现状锚点 | 最早阶段 |
|------|----------|----------|
| `PersonalityMatchScorer` | `game_routes._score_personality_pair` | M4 |
| `TrustAttestationScorer` | Trust v2 / [TRUST_LAYER](./TRUST_LAYER.md) §6 | M4+ |

---

## 5. 里程碑与验收标准

> **状态图例：** 🔲 未开始 · 🟡 进行中 · ✅ 完成 · ⏸️ 冻结  
> 完成定义以 **验收清单全部勾选** 为准；口头「差不多」不算完成。

### M0 — 抽口不换脑

| 项 | 内容 |
|----|------|
| **目标** | InferencePort + JobMatchScorer 落地；默认行为 = 今日 LLM 打分 |
| **工期参考** | ~1 周 |
| **代码落点** | `inference/*`、`matching/*`；`_call_llm` / `_score_resume_vs_job` 委托 |
| **状态** | 🔲 |

**验收（Done）：**

- [ ] `_call_llm` 行为与切流前一致（同 prompt、同 provider 顺序）  
- [ ] `JOB_MATCH_SCORER` 未设置时走 `llm_v1`（现 prompt 迁入）  
- [ ] `pytest backend/tests/test_job_match_gap.py` 通过  
- [ ] 至少 1 次手工 / 冒烟 match：分数分布非全员默认 50  
- [ ] 日志或响应元数据可区分 `provider` + `scorer=llm_v1`  
- [ ] 本文件修订记录更新为 M0 ✅，并注明合并 PR / commit

### M1 — 无 LLM 可排序

| 项 | 内容 |
|----|------|
| **目标** | `heuristic_v0`：规则/词表特征填满可排序的 11 维；LLM 全挂时列表仍有区分度 |
| **工期参考** | ~1–2 周 |
| **依赖** | M0 ✅ |
| **状态** | 🔲 |

**验收（Done）：**

- [ ] `JOB_MATCH_SCORER=heuristic_v0` 可启动  
- [ ] 拔掉 / 无效化 LLM API Key 后，match API 仍 200，且 top 与 bottom `overall` 可区分（非全体相等）  
- [ ] `JOB_MATCH_EXPLAIN=none` 时解释字段合法为空字符串 / 空列表，不 500  
- [ ] 主 Scorer 失败时按 `JOB_MATCH_FALLBACK` 降级有测例  
- [ ] consent / 配额路径未绕过

### M2 — 影子评估与标注闭环

| 项 | 内容 |
|----|------|
| **目标** | 每次打分可审计落库；内测标注；llm vs heuristic 离线对比 |
| **工期参考** | ~2–3 周 |
| **依赖** | M0 ✅；M1 建议完成（可并行起表） |
| **状态** | 🔲 |

**拟议落库（名称可调，须进迁移/schema 说明）：** `match_score_events`  
建议字段：`id`, `created_at`, `user_id`(可空), `resume_hash`, `job_id`, `scorer`, `provider`, `model`, `scores_json`, `pipeline_version`

**验收（Done）：**

- [ ] 生产或内测环境打分写入事件表（或等价审计存储）  
- [ ] 具备最小标注手段（脚本或内测 UI）：合适 / 不合适（或 1–5 分）  
- [ ] 标注样本量达到团队约定阈值（**默认门槛：≥ 200 条**；变更须改本表并记录决议）  
- [ ] 产出一份对比摘要（Spearman 或 top-3 命中；存 `docs/` 或内部报告并链接到修订记录）  
- [ ] 影子双写不得在未灰度时改变用户可见排序（配置显式开启才切流）

### M3 — 垂域精排 `ranker_v1`

| 项 | 内容 |
|----|------|
| **目标** | 自研精排定序；LLM 仅可选解释；可灰度 |
| **工期参考** | ~4–6 周（含特征与离线训） |
| **依赖** | M2 标注达标 |
| **状态** | 🔲 |

**约束：**

- 在线服务优先加载已训好的轻量模型（如 sklearn / LightGBM / 小 MLP）；训练在离线脚本。  
- Hybrid：`ranker_v1` 出分；`JOB_MATCH_EXPLAIN=llm` 时补文案。

**验收（Done）：**

- [ ] `JOB_MATCH_SCORER=ranker_v1` 可在内测环境启用  
- [ ] 在 M2 标注集上，top-3 命中不低于 `llm_v1` 的约定比例（**默认：≥ 90%**；变更须书面决议写入修订记录）  
- [ ] 单次 match 延迟与 LLM 调用成本相对 `llm_v1` 有可引用数字（报告链接）  
- [ ] 灰度开关与回滚路径文档化（切回 `llm_v1` / `heuristic_v0`）  
- [ ] `PIPELINE_VERSION` 若语义变化则 bump，并更新 [SMOKE_MATCH_REPORT](./SMOKE_MATCH_REPORT.md) 或等价冒烟

### M4 — 同构扩展（可选，不阻塞上线）

| 项 | 内容 |
|----|------|
| **目标** | 人格匹配、Trust 评分复用同一端口模式 |
| **依赖** | M0；产品排期 |
| **状态** | 🔲 |
| **验收** | 各端口有独立测例；Trust 仍遵守「无可直接展示的信用分」红线 |

---

## 6. 推荐切流与降级（运维可审计）

```text
默认（生产）:
  JOB_MATCH_SCORER=llm_v1
  JOB_MATCH_EXPLAIN=llm
  LLM_PROVIDER_ORDER=<区域策略：云端 + ollama 兜底>

降级链:
  主 Scorer 失败 → JOB_MATCH_FALLBACK（默认 heuristic_v0）
  Inference 失败 → 保留已出分数；解释字段空

灰度:
  内测 cohort → ranker_v1
  M2 影子双写 → 只写事件表，不改可见序（除非显式切主 Scorer）
```

**禁止：** 在实体许可 / 审核冻结面（见 [YEDALL_LOOMA_BOUNDARY](./YEDALL_LOOMA_BOUNDARY.md)）上，以「算法发版」为名改审核敏感营销页。

---

## 7. 与纲领的对应关系

| 本文件 | 纲领 / 信任层 |
|--------|----------------|
| M0–M1 | 技术栈「LLM 可换」工程化；大陆/海外 provider 已存在，缺端口抽象 |
| M2–M3 | 职位匹配垂域自研；**不是** Trust v2 本体 |
| M4 Trust 端口 | [TRUST_LAYER](./TRUST_LAYER.md) v2「可训练模型 + 人工抽检」 |
| 非目标 | [MANIFESTO](./MANIFESTO.md)「不做会员=信用分」 |

---

## 8. 决策记录（Decision Log）

| 日期 | 决议 | 决议人 / 场合 | 备注 |
|------|------|---------------|------|
| 2026-07-23 | 采纳「L1 Inference + L2 JobMatchScorer」双端口；里程碑 M0–M3 为卡脖子主路径；不训通用基座 | 草案写入本文件 | 待团队确认后将状态改为「已批准」 |
| 2026-07-23 | M2 标注默认门槛 ≥ 200；M3 top-3 ≥ 90% of llm_v1 | 草案默认值 | 可用本表新行覆盖 |

---

## 9. 修订记录

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| 0.1 | 2026-07-23 | 工程草案 | 首版：问题、非目标、接口、M0–M4 验收、切流、决策日志 |

---

## 10. 批准栏（审计用）

| 角色 | 姓名 | 日期 | 签名 / 确认 |
|------|------|------|-------------|
| 产品 / 场景 | | | ☐ 批准 · ☐ 有条件批准 · ☐ 驳回 |
| 工程 | | | ☐ 批准 · ☐ 有条件批准 · ☐ 驳回 |
| 合规 / 边界（如涉及对外宣称「自研算法」） | | | ☐ 批准 · ☐ 不适用 |

**有条件批准须在下方写明条件；驳回须写明阻塞项。**

条件 / 阻塞项：

```text
（空白）
```
