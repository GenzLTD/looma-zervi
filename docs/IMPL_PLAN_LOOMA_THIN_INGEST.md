# Looma 侧实施计划（薄改 · 先做）

> **日期：** 2026-08-08  
> **范围：** 只做「收得下、降得住」——**不**把 OCR/MinerU 整段搬进 Looma  
> **对照版：** `/Users/jason/SurfaceZervi/GitHub/xiajason/zervi-rust`（`llm-gateway` 多 provider / 降级思路）  
> **配对计划：** [IMPL_PLAN_DEMOPETER_LOCAL_PARSE.md](./IMPL_PLAN_DEMOPETER_LOCAL_PARSE.md)  
> **验收 / PR：** 本侧完成后由 Agent 交叉验收并开 PR → `main`

---

## 1. 目标与非目标

| 目标 | 非目标 |
|------|--------|
| 已解析文本/markdown **可不经云端 LLM** 入库并返回稳定 `resume_id` | 在 Looma 内重建 Rust upload 全流水线 |
| LLM provider 顺序可含 **Ollama**，失败可降级而非整链死 | 默认砍掉 DeepSeek、强迫全站本地推理 |
| 为 DemoPeter 预留「推送已解析简历」窄入口（或复用现 API） | DemoPeter UI / 本地 Chroma |
| 匹配报告 + Ask 摘要注入（A1/A2 已完成）保持可用 | 用户全文进 Chroma |

**客户感知：** 上传更稳；深度质量仍默认云端；本地仅作降级/终端推送路径。

---

## 2. 工作包（WBS）

### L-P0-1 · 解析与 persist 解耦（核心）

**现状问题：** `upload` 在 LLM 结构化失败时短路，不进 Step 3 persist → 无 `resume_id`，下游全断。

| 步骤 | 动作 | 文件锚点 |
|------|------|----------|
| 1 | 定义入库最低门槛：`markdown`（或纯文本）非空即可 persist | `resume_routes.py` |
| 2 | LLM 结构化失败：仍入库，`extracted` 可为空/部分；响应带 `status=partial` + `hint` | 同上 |
| 3 | LLM 完全不可用：同上，不 503 掉整次上传（或 200+partial） | 同上 |
| 4 | 保持 A1：`resume_id=lastrowid`，`file_path=resume/{user}/{id}_{safe}`，owner 过滤 | 已完成，回归即可 |

**验收：**

```text
DEEPSEEK 不可用 + Ollama 不可用时：
  POST /v1/resume/upload（或 ingest 文本）→ 200
  → resume_id 为数字字符串
  → GET /v1/resume/analysis?resume_id=N 非 404
  → LIST 能看见该条
```

> **状态：✅ 已完成** — `upload_resume()` 改为 Step 2 persist first → Step 3 LLM best-effort。
> 响应新增 `status: "complete" | "partial"` + `hint` 字段。
> 下游 `list_resumes` / `analysis_resume` 已兼容 `extracted` 缺失（默认 `{}`）。

### L-P0-2 · 已解析文本入口（给 DemoPeter）

任选其一（优先改动小的）：

| 方案 | 说明 |
|------|------|
| **A（推荐）** | 扩展 `POST /v1/resume/parse`：在现有 parse 后 **持久化** documents，返回 `resume_id`（今日 parse 不落库） |
| **B** | 新增 `POST /v1/resume/ingest`：`{ markdown, filename?, extracted? }` → 只入库，不调 LLM |

| 步骤 | 动作 |
|------|------|
| 1 | 实现 A 或 B；鉴权 + `jobseeker_core` consent |
| 2 | shared-core 补类型 / `createResumeApi` 方法 |
| 3 | 单测：无 LLM key 时 ingest/parse-persist 成功 |

**验收：** DemoPeter（或 curl）只推 markdown → 得到 `resume_id`，不依赖云端 LLM。

> **状态：✅ 已完成** — 选择方案 B（新增 `POST /v1/resume/ingest`），因 DemoPeter 载荷为 `{ markdown, filename, extracted }` 不同于 `/parse` 的 `{ text }`。
> `resume_routes.py` 新增 `ingest_resume()` 端点：auth + consent → 直接 persist → 返回 `{ resume_id, status }`。
> `ResumeIngestRequest` / `ResumeIngestResponse` 类型已加入 shared-core 并导出。
> `createResumeApi.ingest()` 方法已就绪。

### L-P0-3 · Provider 顺序与 Ollama 降级（对照 llm-gateway）

| 步骤 | 动作 | 锚点 |
|------|------|------|
| 1 | 文档化推荐：`LLM_PROVIDER_ORDER=ollama,deepseek`（内测）或 `deepseek,ollama`（生产默认云端） | `.env.example`、运维备注 |
| 2 | 确认 `_call_llm` 已按 order 轮询；Ollama 失败不拖垮整个请求的「文本入库」路径 | `central_brain.py` |
| 3 | `/health` 已暴露 `providers_configured`：验收脚本读此字段 | 现有 |

**验收：** 仅 Ollama 可用时，improve/analysis 类可走本地；upload 文本入库不依赖任一 LLM。

> **状态：✅ 已完成** — `.env.example` 已添加 provider 顺序策略注释（生产/内测/离线三种推荐组合）。
> `_call_llm` 已按 `LLM_PROVIDER_ORDER` 轮询降级，无需代码改动。
> `/health` 已暴露 `providers_configured`。

### L-P0-4 · 匹配报告链路回归（不新开功能）

| 步骤 | 动作 |
|------|------|
| 1 | Jobs 保存报告带 `resume_id`（A2 已接） |
| 2 | Ask `?report=` 摘要注入（A2 已接） |
| 3 | 用 **ingest 产生的 resume_id** 跑：匹配 → 保存报告 → Ask |

**验收：** 全链路不依赖「云端 LLM 解析成功」这唯一前提。

> **状态：✅ 已验证可行** — A1/A2 已完成（见 commit `4bffeea`），
> ingest 产生的 `resume_id` 与 upload 产生的 `resume_id` 格式相同，
> 匹配报告链路的 `report_id`→Ask 注入不变。新增 4 个回归测试覆盖。
> **⚠️ 全链路 E2E 需 LLM 可用（LLM 不可用时匹配报告本身不可用，非本改动引入）。**

### L-P0-5 · 文档与契约

| 交付物 | 状态 |
|--------|------|
| 本计划勾选更新 | ✅ 各包状态已标记 |
| `IMPL_GUIDE_TERMINAL_RAG_AND_ASK_CONTEXT.md` 链到 L-P0-2 入口 | ✅ ingest 端点文档化 |
| 若有 API 变更：changelog 一小段 / shared-core 类型 | ✅ `ResumeIngestRequest` / `ResumeIngestResponse` 已导出 |

---

## 3. 明确不做（本 PR 拒绝清单）

- [ ] PaddleOCR / MinerU / pyresparser 进程塞进 Looma 容器  
- [ ] Consul / 拆微服务  
- [ ] 用户简历写入 `looma_knowledge`  
- [ ] 替换支付 / Trust / Game  

---

## 4. 测试与验收（Agent 开 PR 前）

| ID | 用例 | 通过标准 |
|----|------|----------|
| T1 | 无 LLM persist | upload/ingest → `resume_id` |
| T2 | owner 隔离 | 他用户 analysis/delete 404 |
| T3 | parse/ingest → match-report → Ask report_id | 200 + 回答可引用摘要（LLM 可用时）或至少报告已存 |
| T4 | 回归 `test_resume_id_contract` + `test_match_reports` | 全绿 |
| T5 | health | `providers_configured` 字段仍在 |

**PR 标题建议：** `feat(resume): decouple persist from LLM + ingest path for terminal push`

**PR 描述必含：** 对照 zervi-rust 的哪些点（仅降级/多 provider，非整仓）；与 DemoPeter 计划的接口约定（字段表）。

---

## 5. 与 DemoPeter 的接口冻结（Looma 先承诺）

DemoPeter → Looma 最小载荷：

```json
{
  "markdown": "...",
  "filename": "resume.pdf",
  "extracted": { }
}
```

响应：

```json
{
  "resume_id": "123",
  "status": "stored" | "processed"
}
```

- `stored`：仅 markdown 入库（无 extracted）
- `processed`：含 extracted 入库

字段变更须两边计划同步改一版号（本文件修订表）。

---

## 6. P2 · Application（投递关联 · HR 可见）

| 端点 | 说明 |
|------|------|
| `POST /v1/application` | `{resume_id, job_id, enterprise_id?}` → 投递记录（需 `application_submit` / `jobseeker_core`） |
| `GET /v1/application` | 求职者自己的投递列表 |
| `DELETE /v1/application/<id>` | 撤回；HR 列表不再返回简历正文 |
| `GET /v1/jobs/<job_id>/applications` | HR（职位 owner）查看活跃投递 + 简历摘要 |
| `POST /v1/jobs/seed-demo` | 将演示职位持久化并归属当前用户（解决 jobs:[] / mock 无 owner） |

撤回后：`status=withdrawn`，HR 侧 `resume.markdown/extracted` 置空并标 `redacted`。

---

## 7. 修订

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1 | 2026-08-08 | 首版：薄改 Looma，先于 DemoPeter |
| 0.2 | 2026-08-08 | L-P0-1~L-P0-5 全部落地；上传 persist 解耦 + ingest 端点 + 测试 |
| 0.3 | 2026-08-08 | P2：applications 表 + API + seed-demo + 撤回对 HR 正文脱敏 |
