# 会话记录 · 2026-08-08

> **范围：** 境内 Deploy 收官、信任档案小程序、匹配/RAG 存储核查、仓库考古、DemoPeter↔T-space 打通设想  
> **性质：** 事实与结论备忘，非规格书

---

## 1. 工程交付（当日已完成）

| 项 | 结果 |
|----|------|
| PR #8 `feat/timeline-phase1` → `main` | 已 merge（`d89aab6`） |
| 境内 Deploy #31234505019 | success → `1.14.202.161` |
| 关键提交在 main | 含闭环 P0、e2e 修复、`112422d` 等 |
| 小程序信任档案 | `pages/trust` + Hub/Match 入口；`99dc478` |
| M-4 文档校准 | `ZERVI_GENZER_IMPLEMENTATION.md` v1.1（v0 不阻塞） |
| 流水线说明 | `docs/PIPELINE_MAIN_OVERSEAS_CI.md` |
| 生产库 SQL 验收 | `fleets.invite_code` 在；`idx_trust_attestations_claim` 在 |
| 后续 push（如 `7fa0b63` / `ac5005e`） | Deploy 继续全绿 |

**健康检查口径：** 境内用 `http://1.14.202.161/health`（不是 `/v1/health`）。

**未做完（人工）：** 浏览器冒烟（登录→信任档案→双账号匹配→T 空间导入）；小程序体验版/上架。

---

## 2. 简历 / JD / 匹配报告 · 存储与 Ask（核查结论）

| 对象 | 存储 |
|------|------|
| 简历 / JD | SQLite `documents`（`metadata` 内 extracted/markdown；原文件不落盘） |
| 匹配报告 | `match_reports` + `match_report_items`（快照，供 Reports 预览） |
| 前端桥 | localStorage `saas-resume-match-text` |
| Chroma | 产品知识库；**不索引**用户简历/JD/报告 |

- 报告预览：读 `match_reports` 快照，不重跑匹配。  
- Ask/RAG：上下文无 `resume_id` / `report_id`；`rag` 只查 Chroma → **匹配后「接着问」当前接不上。**  
- 已见缺陷：`resume_id` 返回 UUID 与 AUTOINCREMENT 行 id 不一致；简历 `file_path=文件名` UNIQUE 可能导致同名再传丢持久化。

**若修「匹配后接着问」：** 优先报告摘要注入 Ask（`report_id` / snapshot），不做默认用户全文进向量库。

---

## 3. 仓库考古（本地路径）

| 路径 | 是什么 | 对终端/本地 RAG 的可用性 |
|------|--------|--------------------------|
| `.../xiajason/zervi-rust` | JobFirst 云端 Rust 微服务（MySQL + upload + llm-gateway） | 可抽解析/LLM 适配；**不是**终端壳 |
| `.../szpeter2026/DemoPPI` | PPI/共识 MVP；研讨记录定为终端机参考 | 信号/共识向；数据在 Supabase |
| `.../szpeter2026/DemoPeter` | 本地知识库（SQLite + Chroma + RAG） | **本地文档 + RAG 数据面**首选 |
| `looma-zervi` | 现网 API + PlanetX + T-space | 云端工作台与契约 |

研讨记录真源：`DemoPPI/docs/TEAM_DISCUSSION_GENZER_TERMINAL_2026-07-12.md`。

**提取原则（不展开论证）：** 从 rust/looma **抽库与契约**；终端壳与本地数据面用 DemoPPI/DemoPeter 线新建或组合，不整仓硬合并。

---

## 4. DemoPeter ↔ T-space 打通（当日结论）

**目标形态（简述）：** DemoPeter 持本地原文与向量；显式推送选定内容/摘要到 T-space 做匹配与报告；Ask 深度问答优先本地 RAG。

| 方案 | 结论 |
|------|------|
| HTTPS + JWT 调现有 `/v1/resume/*`、`/v1/jobs/*`、`/v1/match-reports`（或窄同步 API） | **主路径，可行** |
| SSH 隧道（本机 DemoPeter ↔ 云机） | **运维/自托管/联调可用** |
| SSH 作为普通用户默认同步总线 / 整库互拷 | **不推荐** |

下一步若做：先定「可上云字段表」+ 最小「推送简历摘要 → 匹配 → 回写 report_id」闭环；SSH 仅用于联调。

---

## 5. 待办快照（会话结束时）

- [ ] 内测机人工冒烟  
- [ ] 小程序体验版联调 / 上架节奏另排  
- [ ] （可选）Ask 注入最近 `match_reports` 摘要  
- [ ] （可选）修 `resume_id` 与 `file_path` 持久化契约  
- [ ] （可选）DemoPeter → T-space 最小同步 POC  

---

## 6. 相关链接与路径

- PR：https://github.com/szpeter2026/looma-zervi/pull/8  
- Deploy：https://github.com/szpeter2026/looma-zervi/actions/runs/31234505019  
- 流水线说明：`docs/PIPELINE_MAIN_OVERSEAS_CI.md`  
- DemoPPI：`/Users/jason/SurfaceZervi/GitHub/szpeter2026/DemoPPI`  
- DemoPeter：`/Users/jason/SurfaceZervi/GitHub/szpeter2026/DemoPeter`  
- zervi-rust：`/Users/jason/SurfaceZervi/GitHub/xiajason/zervi-rust`
