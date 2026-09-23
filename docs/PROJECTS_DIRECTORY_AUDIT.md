# Projects 目录勘查记录与处置建议

> **版本：** 2.0 · **复勘日期：** 2026-09-05（首勘 1.0：2026-07-03）
> **状态：** 仅文档记录，**未执行任何删除或迁移**
> **复勘方式：** 目录角色人工核对 + `du -sh` 实测（2026-09-05）
> **同步副本：**
> - `looma-zervi/docs/PROJECTS_DIRECTORY_AUDIT.md`
> - `szbolent-portal/docs/PROJECTS_DIRECTORY_AUDIT.md`
> **关联：** [DUAL_REPO_WORK_GUIDE.md](./DUAL_REPO_WORK_GUIDE.md) · portal 专用：`LINEAGE.md`、`INTEGRATION.md`（同目录）

---

## 1. 勘查目的

时隔两个月复勘 `/Users/jason/Projects` 根目录。1.0（2026-07-03）勘查时根目录以 **looma-zervi × szbolent-portal 双仓** 为主；此后新增了 **gfcc 共同体内核线、Genzer 终端线、智能大脑合规线、FlexJob 外包线** 等多棵活跃主线，旧的「双仓中心」视角已不覆盖现状，故更新分类、大小与删留审定。

**本轮结论（与 1.0 一致）：** 占用大头主要为 Rust `target` 构建产物与知识库/向量运行数据，**全部暂不删除**；可清理项以「可重建构建产物」「冗余压缩包」「过期副本」为主，仅作记录，供日后磁盘整理参照。

---

## 2. 勘查范围

| 范围 | 路径 | 是否纳入 |
|------|------|----------|
| 工程根目录 | `/Users/jason/Projects` | ✅（一级全部，`du -sh` 实测） |
| 根目录散文件（.md / .yaml / .rar / .png） | 同上 | ✅ |
| SurfaceZervi 博物馆登记 | `/Users/jason/SurfaceZervi` | ❌ 本轮未细查（维持 1.0 结论） |

> 注：隐藏目录（各仓 `.venv`/`.git` 等）参与 `du` 计数但不在一级列表体现。

---

## 3. 复勘摘要（相对 1.0 的主要变化）

| # | 变化 | 说明 |
|---|------|------|
| 1 | **新增活跃主线 ×6** | `gfcc/`（共同体内核）、`genzer/`+`zervi-genzer/`（Genzer 终端决策线）、`wukong-core/`+`cortex-mcp/`+`genz-brain-m2/`（智能大脑合规线）、`FlexJob/`（外包承揽）、`genz-web/`（海外 genz.ltd 营销线）、`kb_corpus/`+`poetry_src/`（语料线） |
| 2 | **looma-zervi 本机活跃树已迁 `~/THOMAS/looma-zervi`** | Projects 内副本（2.0G）保留为生态工作副本/文档同步源；本地起 API 唯一入口是 THOMAS 树（`./dev.sh`） |
| 3 | **szbolent-portal 非纯 SPA** | 实测内含 Rust `backend/`（`target/` 2.1G，可 `cargo clean` 重建），Vue SPA 本体（`src/` 仅 544K） |
| 4 | **压缩包存在双份副本** | 根目录 `poetry_full.rar`（177M）+ `中华诗词汇总源数据.rar`（61M）与 `poetry_src/` 内同名文件重复，各留一份即可 |
| 5 | **backup_archive 备份策略已更新** | 源码/配置备份自 2026-09-04 起改落外置盘 `/Volumes/SHARED/cloud-backup/`，`backup_archive/`（3.5G）为旧机备份，可迁盘归档 |
| 6 | **根目录新增决策/契约散文件** | `candidates-*.yml`、`dashboard-beta-free.png`、`BRAND_VI_GUIDELINES.md` 等属 looma 定价/品牌资产 |

---

## 4. 核心保留 · 活跃工程（勿删）

### 4.1 Looma / Zervi 生态线

| 路径 | 实测大小 | 角色 |
|------|----------|------|
| `looma-zervi/` | 2.0G | 生态主仓工作副本：Flask API 真源、PlanetX/T-space 前端、微信小程序、诗词/RAG/支付、契约；`backend/venv` 340M、`data/poetry_full` 300M（Chroma 运行时依赖，勿删）、`data/chroma_models` 170M |
| `genz-web/` | 76M | 海外 genz.ltd 营销 SPA（Stripe 定价），`node_modules` 75M 可重建 |
| `zervi-genzer/` | 13M | 三条战略线决策/文档仓（契约化身份/共识裂变/信任记忆体 + Genzer 终端路线） |
| `genzer/` | 2.1M | Genzer Terminal 软件终端源码副本（前 DemoPPI；依赖未装），共识网络链下快路径 |

### 4.2 GFCC 共同体内核线

| 路径 | 实测大小 | 角色 |
|------|----------|------|
| `gfcc/` | 3.7G | 格契契约层真源 + 单栈多服务（内核 :5211 / tatha :5210 / demopeter :5220 / agentmemory :3210）；`services/demopeter` 2.4G（知识库 + 向量数据）、`services/tatha` 1.3G（含服务依赖与运行数据），均属运行资产 |
| 部署 | — | 天翼 14.29.216.219 `/data/gfcc` = 上云主节点（远程树，非本目录） |

### 4.3 智能大脑 / 合规治理线

| 路径 | 实测大小 | 角色 |
|------|----------|------|
| `wukong-core/` | 232K | 认知内核黑匣子（门控/轨迹/比对）；`policy_rules.yaml` 为**合规规则单源**（cortex-mcp 运行时按 mtime 重载） |
| `cortex-mcp/` | 261M | MCP 记忆服务（FastMCP + pgvector）；大头为 `.venv` 261M |
| `genz-brain-m2/` | 85M | 跨境合规判定 **Rust↔Python 对拍验证资产**（64 组合矩阵）；`rust-parity/target` 84M 可重建 |

### 4.4 Bolent 诗词门户线

| 路径 | 实测大小 | 角色 |
|------|----------|------|
| `szbolent-portal/` | 2.4G | www.szbolent.cn 门户壳（Vue SPA；个人备案·内容站）；内嵌 Rust `backend/`（`target/` 2.1G 可 `cargo clean`）、`node_modules` 262M 可重建 |
| `poetries-h5/` | 229M | UniApp 诗词移动端（Bolent API）；`node_modules` 227M 可重建 |
| `PoetriesGap/` | 316K | 诗词立项建议书（`Poetries_立项建议书_V1.0(2).docx` + deploy），历史立项资产，可归档保留 |

### 4.5 JobFirst 主线工作区

| 路径 | 实测大小 | 角色 |
|------|----------|------|
| `PlanetX/` | 4.9G | JobFirst 求职 AI 助理主线工作区（jobfirst-claw / zervi-rust / zervi.test）；大头为 Rust 构建产物，可 `cargo clean` |

> 命名提示：与 looma 生态 C 端**品牌包** `packages/planetx` 同名，二者不同物。

### 4.6 FlexJob（独立业务线）

| 路径 | 实测大小 | 角色 |
|------|----------|------|
| `FlexJob/` | 6.4G | 深伯乐「项目外包承揽」平台 MVP（Rust，抽核自 zervi-rust；仅 Gitee `szbenyx/FlexJob`）；`target/` 4.5G 可 `cargo clean`、`admin-web/` 1.9G（node_modules 大头） |

---

## 5. 数据 / 语料 / 验收资产（保留）

| 路径 | 实测大小 | 说明 |
|------|----------|------|
| `kb_corpus/` | 3.0G | 知识库语料：法律法规汇编多批、名著/教材、Python 素材 719M、普林斯顿数学指南 517M；对应 demopeter/gfcc 知识库导入源 |
| `poetry_src/` | 532M | 诗词语料源：`诗词库/` 294M + 两个 `.rar` 副本（与根目录重复，见 §7 #3） |
| `looma-zervi/data/` | 470M | `poetry_full` 300M（Chroma，后端硬依赖）+ `chroma_models` 170M |
| `screenshots/` | 6.3M | 页面/验收截图 |
| `dashboard-beta-free.png` | 68K | beta-free 定价验证截图（与 `candidates-*.yml` 同属 looma 定价资产） |

---

## 6. 根目录散文件处置建议

| 文件 | 实测大小 | 建议 |
|------|----------|------|
| `api.yaml` / `planetx-auth.yaml` | 36K / 4K | API/认证契约草稿；按 1.0 §5.5 建议迁入 `looma-zervi/docs/` 作契约真源 |
| `Tatha+DemoPeter_融合决策*.md`（×2） | 52K | 历史决策，结论已体现在 looma 架构；可归档至 SurfaceZervi/docs |
| `CONSISTENCY_*.md`、`DECISION_RESPONSE*`、`JASON_DECISION_ACK.md`、`DUAL_REPO_SYNC_STATUS.md` | ~60K | 双仓协同决策/状态记录；保留（可随 doc 整理收进对应仓 docs） |
| `candidates-after-wait.yml`、`candidates-beta-free.yml` | 8K | looma 订阅/邀请候选画像（beta-free 线） |
| `BRAND_VI_GUIDELINES.md` | 24K | 品牌 VI 规范，保留 |

---

## 7. 审定清单（2026-09-05 · 实测大小 · 均未执行）

### 7.1 可重建构建产物（仓库保留，定期 clean 即可，非删除）

| # | 路径 | 可释放 | 命令 |
|---|------|--------|------|
| 1 | `FlexJob/target/` | 4.5G | `cargo clean` |
| 2 | `szbolent-portal/backend/target/` | 2.1G | `cargo clean` |
| 3 | `PlanetX/` 内 Rust target（zervi-rust 等） | 约 1G+ | `cargo clean`（按仓执行） |
| 4 | `genz-brain-m2/rust-parity/target/` | 84M | `cargo clean` |
| 5 | `looma-zervi/frontend/node_modules` + 各前端 `node_modules` | 数百 M | `pnpm/npm ci` 可重建（非必要时不动） |

> 运行依赖（`looma-zervi/backend/venv` 340M、`cortex-mcp/.venv` 261M、gfcc 各服务数据卷）**不建议清**：重建成本高。

### 7.2 冗余副本（建议各留一份）

| # | 路径 | 可释放 | 说明 |
|---|------|--------|------|
| 1 | `poetry_full.rar`（根） | 177M | 与 `poetry_src/poetry_full.rar` 重复；已解压进 `looma-zervi/data/poetry_full/` |
| 2 | `中华诗词汇总源数据.rar`（根） | 61M | 与 `poetry_src/` 内同名重复；SurfaceZervi 有语料快照 |

### 7.3 过期 / 无关（未来可删或迁盘）

| # | 路径 | 可释放 | 理由 |
|---|------|--------|------|
| 1 | `backup_archive/` | 3.5G | 旧机备份（BACKUP_SERVBAY / workspaces_backup）；2026-09-04 起备份改落 `/Volumes/SHARED/cloud-backup/`，本地副本可迁盘归档 |
| 2 | `planex-miniprogram/` | 492K | 旧 JS 小程序；真源 `looma-zervi/frontend/packages/miniprogram`（TS，功能更全） |
| 3 | `tatha-frontend/` | 480K | 静态预览；Tatha RAG 已融入 Looma `backend/src/rag/` |
| 4 | `GBZ185_原文提取/` + `.zip` | 212K | 职业卫生标准原文提取，与工程无引用 |
| 5 | `300662科锐国际/` | 32M | 财报 docx，无代码引用 |
| 6 | `数据分析与python实战-代码/` | 30M | Python 教程 notebook，无项目引用 |
| 7 | `test_write` | 0B | 空文件，测试残留 |

**7.1–7.3 全部执行（含 clean，不含运行依赖）：约 11G+ 可释放；其中仓库删除类仅约 3.8G，其余为可重建构建产物。**

**审定结论：暂不删除，仅本文档记录。** 与 1.0 保持一致。

---

## 8. 明确不建议删除

- 活跃工程全列（§4.1–4.6）：`looma-zervi/`、`szbolent-portal/`、`gfcc/`、`genzer/`、`zervi-genzer/`、`PlanetX/`、`genz-web/`、`wukong-core/`、`cortex-mcp/`、`genz-brain-m2/`、`FlexJob/`、`poetries-h5/`
- 语料与运行数据：`kb_corpus/`、`poetry_src/诗词库/`、`looma-zervi/data/`（poetry_full / chroma_models）
- 决策/品牌资产：根目录 §6 所列散文件
- SurfaceZervi（含 snapshots、archive、MANIFEST）——维持 1.0 结论

---

## 9. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-07-03 | 首勘；决定暂留所有项，仅文档记录 |
| 2.0 | 2026-09-05 | 复勘：新增 6 条活跃主线分组（GFCC/Genzer/智能大脑/FlexJob/海外/语料）；`du -sh` 实测刷新全表；记录 looma 活跃树迁 THOMAS、szbolent-portal 含 Rust backend、.rar 双份副本、backup_archive 备份策略更新；结论维持暂不删除 |
