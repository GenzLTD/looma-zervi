# DemoPeter 侧实施计划（本地解析 · 后做）

> **日期：** 2026-08-08  
> **仓路径：** `/Users/jason/SurfaceZervi/GitHub/szpeter2026/DemoPeter`  
> **范围：** 解析前移本地、智能分层降级、推送摘要到 T-space；**不**改 Looma 为重解析后端  
> **对照版：** `/Users/jason/SurfaceZervi/GitHub/xiajason/zervi-rust`（`upload-service` 文档路由 / ATS 流程）  
> **前置依赖：** Looma [IMPL_PLAN_LOOMA_THIN_INGEST.md](./IMPL_PLAN_LOOMA_THIN_INGEST.md) **L-P0-1 + L-P0-2 已合并**（有稳定 ingest/`resume_id`）  
> **验收 / PR：** 本侧完成后由 Agent 验收；PR 开在 **DemoPeter 仓**（或约定的交付远端），并在 looma 侧留联调说明 PR/注释

---

## 1. 目标与非目标

| 目标 | 非目标 |
|------|--------|
| 本地完成「文件 → 文本 →（可选）结构」 | 把 DemoPeter 变成第二套 SaaS |
| Ollama / 规则分层降级，云端 LLM 可选 | 强制用户必须有云端 key 才能导入 |
| 一键推送到 Looma → 匹配/报告 | SSH 默认同步、整库互拷 |
| `WEB_PORT=5210` 与 Looma `:5200` 并行 | 占用 5200 |

**客户感知：** 终端侧导入更稳、可离线粗用；T-space 仍是工作台，深问在本地 RAG。

---

## 2. 工作包（WBS）

### D-P0-0 · 环境与端口

| 步骤 | 动作 |
|------|------|
| 1 | `.env`：`WEB_PORT=5210`（避开 Looma） |
| 2 | 文档写明：本机联调 `TSPACE_API_BASE=http://127.0.0.1:5200` |
| 3 | 确认现有 SQLite + Chroma 路径可写 |

**验收：** DemoPeter 与 Looma 同时 listen，互不抢端口。

### D-P0-1 · 本地解析路由（对照 Rust upload）

对照 `zervi-rust/upload-service` 的「按类型分流」思想，在 DemoPeter **用 Python 实现等价分层**（不必嵌入 Rust 二进制）：

| 层 | 输入 | 处理 | 输出 |
|----|------|------|------|
| L0 | PDF/DOCX/MD/TXT | 现有 `doc_processor` + 必要增强 | markdown / plain |
| L1 | 扫描件 / 失败 PDF | 可选：系统 OCR 或后续接 MinerU 边车 | markdown |
| L2 | 需要结构时 | 本机 Ollama JSON 抽取；失败则空 `extracted` | extracted? |

| 步骤 | 动作 | 锚点（DemoPeter） |
|------|------|-------------------|
| 1 | 统一「导入成功 = 有文本入库」；结构失败不挡导入 | `doc_processor` / `kb_service` / upload API |
| 2 | 增加 `parse_status`: `text_ok` \| `structured_ok` \| `partial` | DB 元数据字段或 JSON |
| 3 | 对照 Rust：记录「用了哪条路由」到日志，便于验收 | logging |

**验收：** 无云端 key 时，PDF/MD 仍能进知识库并本地检索。

### D-P0-2 · 智能分层降级（生成侧）

| 优先级 | 引擎 | 用途 |
|--------|------|------|
| 1 | 规则/模板 | 极短摘要、技能关键词 |
| 2 | 本机 Ollama | 结构抽取、本地 Ask |
| 3 | 云端 API（可选配置） | 用户显式「精析」 |

| 步骤 | 动作 |
|------|------|
| 1 | `AI_PROVIDER` / fallback 顺序写清（对照 llm-gateway 的 order） |
| 2 | UI 提示当前引擎：「本地 / 云端 / 仅文本」 |
| 3 | 失败不吞错误：可重试「仅文本已保存」 |

**验收：** 断网或无云端 key：导入 + 本地问答仍可用；有 Ollama 时结构质量可接受。

### D-P0-3 · 推送到 T-space（依赖 Looma L-P0-2）

| 步骤 | 动作 |
|------|------|
| 1 | `connectors/tspace_client.py`：JWT（粘贴或登录）+ `ingest`/`parse-persist` |
| 2 | 文档详情按钮：「推送到 T-space」 |
| 3 | 成功后保存 `resume_id`、可选打开 `http://localhost:5174/jobs` |
| 4 | 推送载荷遵守 Looma 冻结字段（markdown + filename + extracted?） |

**验收：**

```text
DemoPeter 导入简历 → 推送 → Looma 返回 resume_id
→ T-space 匹配 → 保存报告 → （可选）report_id 回写本地元数据
```

### D-P0-4 · 本地 RAG 与报告摘要分工

| 问题类型 | 回答位置 |
|----------|----------|
| 文档细节 / 多文档综合 | DemoPeter RAG |
| 匹配分数 / 缺口 / 改进计划 | T-space Ask（报告摘要）或把报告摘要拉回本地再问 |

| 步骤 | 动作 |
|------|------|
| 1 | 不把个人库同步进 Looma Chroma |
| 2 | （可选）拉取 match-report 摘要缓存到本地「报告抽屉」 |

---

## 3. 明确不做

- [ ] 在 DemoPeter 内实现支付 / Trust / PlanetX 游戏  
- [ ] SSH 作为默认同步总线  
- [ ] 替换 Looma 成为唯一后端  
- [ ] 第一期强依赖编译 zervi-rust（对照逻辑即可；Rust 边车列为 P1）

---

## 4. 与 zervi-rust 对照清单（实施时勾）

| Rust 能力 | DemoPeter 落地方式 |
|-----------|-------------------|
| 文档类型路由 | Python 分支 + 现有 processor |
| 解析失败不丢文件 | `text_ok` 先入库 |
| llm-gateway 多 provider | `ai_client` fallback 顺序 |
| ATS / 改写 | **P1** 再对照 `ats_optimizer`（本 P0 可不做） |
| MySQL 中心库 | **不做**，坚持本地 SQLite |

---

## 5. 测试与验收（Agent 开 PR 前）

| ID | 用例 | 通过标准 |
|----|------|----------|
| U1 | 端口 | `:5210` 与 Looma `:5200` 并行 |
| U2 | 无云端导入 | 文档进库 + 本地 search/ask |
| U3 | 推送 | 获得 Looma `resume_id` |
| U4 | 联调竖切 | 推送 → T-space 匹配 → 报告（需 Looma 已合 P0） |
| U5 | 回归 | 现有 DemoPeter 导入/问答不坏 |

**PR 建议（DemoPeter 仓）：**  
`feat: local parse tiers + T-space ingest push`

**PR 描述必含：** 依赖的 Looma API（ingest/parse-persist）；端口 5210；对照 rust 的哪些行为。

---

## 6. 两边协作时序

```text
1) Looma PR 合并 + 境内部署（或本地 :5200）
2) DemoPeter 按本计划开发
3) Agent 联调 U3–U4
4) DemoPeter PR；必要时 Looma 小修契约（另开小 PR）
5) 更新 SESSION / IMPL_GUIDE 勾选
```

---

## 7. 修订

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1 | 2026-08-08 | 首版：DemoPeter 后置，对照 zervi-rust |
