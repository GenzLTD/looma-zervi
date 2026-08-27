# 实施指引：终端本地 RAG + 云端报告上下文 Ask

> **日期：** 2026-08-08  
> **目标：** 分轨落地——DemoPeter 持本地 resume/RAG；looma/T-space 只做摘要级「匹配后接着问」+ 修 `resume_id`；**不做**用户文档进 Chroma。  
> **关联记录：** [SESSION_RECORD_2026-08-08.md](./SESSION_RECORD_2026-08-08.md)

---

## 0. 范围与禁区

| 做 | 不做 |
|----|------|
| Ask 注入 `match_reports` 摘要（`report_id` / 最近一份） | 用户简历/JD 写入 `looma_knowledge` |
| 修 `resume_id` = DB `documents.id`；稳定 `file_path` | 把 DemoPeter 整库 SSH 互拷当同步 |
| DemoPeter → T-space **显式推送**摘要/选定文本 | 浏览器 SaaS 假装本地终端 |
| 端口错开（DemoPeter ≠ 5200） | 扩大 Ask 配额绕过 / 静默上传全文 |

**验收一句话：** 云端 Ask 能围绕「刚保存的匹配报告」回答；深度文档问答在 DemoPeter；两端不抢 `:5200`。

---

## 分仓实施计划（2026-08-08）

| 侧 | 计划 | 顺序 |
|----|------|------|
| Looma 薄改 | [IMPL_PLAN_LOOMA_THIN_INGEST.md](./IMPL_PLAN_LOOMA_THIN_INGEST.md) | **先做** → Agent 验收开 PR |
| DemoPeter 本地解析 | [IMPL_PLAN_DEMOPETER_LOCAL_PARSE.md](./IMPL_PLAN_DEMOPETER_LOCAL_PARSE.md) | **后做**（依赖 Looma ingest）→ Agent 验收开 PR |
| 对照版 | `.../xiajason/zervi-rust` | 不整仓上线 |

---

## 阶段 A — 云端最小修复（looma-zervi，约 1–2 天）

### A1. 修 `resume_id` 契约

**文件：** `backend/src/api/routes/resume_routes.py`（upload 持久化段 ~279–301）

| 步骤 | 动作 |
|------|------|
| 1 | `INSERT` 后用 `cursor.lastrowid`（或 `RETURNING id`）作为 `resume_id` |
| 2 | `file_path` 改为稳定唯一键，例如 `resume/{user_id}/{uuid}_{safe_filename}`，避免同名 UNIQUE 撞车 |
| 3 | `DELETE` / `GET analysis` 已按 integer id 查的保持一致；补测「上传 → 用返回 id 再 GET/DELETE」 |
| 4 | （可选）`match_reports.create` 入参支持可选 `resume_id`，Jobs 保存报告时传入 |

**验收：**

```bash
# 伪步骤：upload 返回 resume_id=N → GET/DELETE /v1/resume/... 对 N 成功，不再 404
pytest backend/tests/ -k resume -q
```

### A2. Ask 注入报告摘要（工作台连续性）

**后端**

| 步骤 | 动作 | 锚点 |
|------|------|------|
| 1 | `POST /v1/ask` body 增加可选 `report_id`；无则取当前用户**最近一条** `match_reports`（可加开关 `use_latest_report: true`） | `ask_routes.py` 读 JSON |
| 2 | 用 `MatchReportManager.get_report` 取快照；拼 **短上下文**（硬上限，建议总量 ≤ 4–6k 字符） | `match_report_manager.py` |
| 3 | 上下文字段示例：`resume_snapshot` 截断、Top N items 的 `overall_score` / `match_reason` / `missing_skills` / `gap_analysis` 摘要 | 写入 `context["match_report"]` |
| 4 | `dispatch` / LLM prompt 组装处：若存在 `match_report`，在 system/user 前缀注入「当前匹配报告上下文」；**仍走原 intent**，不要改成个人向量检索 | `central_brain.py` / navigator prompt |
| 5 | 缓存 key 纳入 `report_id`（避免串报告） | `_cache_key` |
| 6 | 无报告时行为与今天完全一致 | 回归 Ask 单测 |

**前端（T-space）**

| 步骤 | 动作 | 锚点 |
|------|------|------|
| 1 | Reports 详情页 / 保存报告成功后：Chat 带上 `report_id` | `Reports.tsx`、`useChatNonStreaming.ts` / `createChatApi` |
| 2 | Jobs「保存为报告」跳转后：URL 已有 `?match=`，Ask 读取同一 id | `Jobs.tsx` → `/reports?match=` |
| 3 | UI 一句提示：「回答将参考当前匹配报告（摘要）」 | 避免用户以为连了全文 RAG |

**验收剧本：**

1. 上传简历 → 匹配 → 保存报告 → 打开报告  
2. Ask：「根据这份报告，我最该补哪三项技能？」  
3. 回答须引用报告中的缺口/分数语义；清空 `report_id` 且无最近报告时，不再假装读过简历  

**明确不做：** `search_chroma` 增加用户 collection；`documents.markdown` 全量塞进 Ask。

### A3. 测试清单（A 阶段出门标准）

- [ ] `resume` upload/list/get/delete id 一致  
- [ ] Ask + `report_id` 有上下文；无 id 无回归  
- [ ] consent `ask_rag` 仍生效；配额仍扣  
- [ ] 缓存不串报告  
- [ ] 不新增 Chroma 用户写入路径  

---

## 阶段 B — DemoPeter 本地数据面（约 3–5 天 POC）

### B0. 本地运行约定

| 项 | 值 |
|----|-----|
| 仓路径 | `/Users/jason/SurfaceZervi/GitHub/szpeter2026/DemoPeter` |
| Web 端口 | **`WEB_PORT=5210`**（避开 looma `:5200`） |
| 数据 | 本地 SQLite + Chroma（仓内 `db/` / `knowledge_base/`） |

```bash
cd /Users/jason/SurfaceZervi/GitHub/szpeter2026/DemoPeter
# .env: WEB_PORT=5210
# 按该仓 README 启动 web / 导入文档
```

### B1. POC 范围（只做一条竖切）

```text
DemoPeter 导入简历 PDF
  → 本地分块 + 向量（已有）
  → 用户点「推送到 T-space」
  → HTTPS + JWT → looma POST /v1/resume/upload
       （或先 POST 纯文本 parse + 自管桥接）
  → （可选）自动打开 T-space Jobs，带预填文本
  → 匹配 + 保存报告（现有 SaaS）
  → 把 report_id 写回 DemoPeter 侧元数据（本地 SQLite 一列即可）
```

深度追问：「结合知识库里其它项目经历解读这份报告」→ **只在 DemoPeter RAG**；T-space Ask 只答报告摘要（阶段 A）。

### B2. 建议新增的薄适配（DemoPeter 侧）

| 模块 | 职责 |
|------|------|
| `connectors/tspace_client.py` | login/register 或粘贴 JWT；`upload_resume`；可选 `create` 不调 |
| UI 按钮 | 文档详情「推送到 T-space」；展示上次 `report_id` |
| 配置 | `TSPACE_API_BASE=http://127.0.0.1:5200`（本机 looma）或内测 IP |
| 字段策略 | 默认可推：markdown/纯文本；**默认不推**整库 embedding |

### B3. 可上云字段（POC 冻结）

| 可推 | 不推 |
|------|------|
| 当前选中文档的提取文本 / markdown | Chroma 全集、其它语料 |
| （匹配后）`report_id`、分数摘要回写本地 | 未授权的并排简历、原始 PDF 强制镜像双份（可选本地保留一份即可） |

### B4. SSH 怎么用（仅联调）

- 需要云机访问你本机 DemoPeter 时：`ssh -R` 反代；**不写进产品默认路径**  
- 日常 POC：本机 DemoPeter `:5210` + 本机 looma `:5200` + T-space `:5174` 即可  

---

## 阶段 C — 接线巩固（有 POC 后再做）

| 项 | 说明 |
|----|------|
| 窄同步 API（可选） | 若 upload 契约别扭，再加 `POST /v1/terminal/push-resume`（摘要 + content-hash + 可选 resume_id） |
| Reports ↔ DemoPeter | 云端保存报告后 webhook/轮询把摘要写回本地「报告抽屉」 |
| DemoPPI | 共识/信号另线；**不阻塞** A/B |
| 从 zervi-rust 抽解析 | 仅当 DemoPeter 解析不够用时再抽 crate/边车 |

---

## 建议排期

| 周次 | 交付 | Owner 建议 |
|------|------|------------|
| W0（**3–4 天** 更稳妥） | A1 → A2 后端 → A2 前端 → A3 回归 | looma 后端 + SaaS Chat/Reports |
| W1 | **B0 + B1** 本机竖切演示（5210↔5200↔5174） | DemoPeter 适配 + 联调 |
| W2+ | B2 打磨、C 按需 | 视内测反馈 |

**A1 补充：** `DELETE /v1/resume/<id>` 与 GET analysis 同为按 `documents.id` 查询；修复时须一并加 `user_id` 归属过滤（已在实现中覆盖）。

---

## 分工接口（避免两仓扯皮）

```text
DemoPeter          HTTPS JWT           looma / T-space
─────────                          ─────────────────
原文 + 向量     ──推送文本/摘要──►   documents / match
本地 RAG 深问                        Ask + report 摘要
report_id 缓存  ◄──回写 id/摘要──   match_reports
```

- **真源文档：** DemoPeter  
- **真源报告（工作台）：** looma `match_reports`  
- **真源配额/登录：** looma JWT  

---

## 完成定义（DoD）

**阶段 A Done**

- [ ] `resume_id` 往返一致  
- [ ] 带报告的 Ask 能引用缺口/分数；不带则与现网一致  
- [ ] 代码路径无「用户文档 upsert Chroma」  

**阶段 B Done**

- [ ] DemoPeter `:5210` 与 looma `:5200` 可并行  
- [ ] 一键推送 → T-space 能完成匹配并保存报告  
- [ ] 同题：本地 RAG 可答文档细节；云端 Ask 只依赖报告摘要  

---

## 快速命令备忘

```bash
# looma API
cd /Users/jason/Projects/looma-zervi && # 按惯例起 :5200

# T-space
cd frontend && pnpm --filter @looma/saas dev   # :5174

# DemoPeter（避开 5200）
cd /Users/jason/SurfaceZervi/GitHub/szpeter2026/DemoPeter
WEB_PORT=5210  # 写入 .env 后启动
```
