# 本地 ServBay vs 天翼云端 部署环境比对报告

- 日期：2026-09-01（2026-09-01 22:38 修订：天翼版本数据按 `check-consistency.sh` 实测更正，原「天翼 git_commit=5fee72e」有误）
- 审阅对象：Windows 侧
- 比对方法：本机实测（health / 端口 / .env）+ `ssh root@14.29.216.219` 天翼只读检查（health / docker inspect / 端口 / 卷）；版本以 `check-consistency.sh` 2026-09-01 22:38 实测为准
- 背景：天翼 `ask` 504 修复（① `DEEPSEEK_API_KEY` 被尖括号包裹 → 401；② 容器重建清掉 chroma ONNX 模型缓存 → 79.3MB 下载卡死）完成后，双端一致性核实

---

## 0. TL;DR

1. **代码版本（实测）**：本地 `feat/tianyi-central-chainb` `5fee72e`；天翼工作区 `d7d92db`、deploy 锚点 `3962cd9`(v1.4.0) —— 本地领先天翼工作区 **14 commits**（Supabase unified auth、LLM ops、weizuo-prep、`/health` git_commit 等），Looma 主环行为仍实测一致。
2. **Looma 主环行为一致**：认证 → consent → ask → DeepSeek 双端实测通过（DeepSeek key 相同且均 HTTP 200）。
3. **天翼实际有 tatha**（`gfcc-tatha-1` 容器，0.0.0.0:5210），仅未被 nginx 代理——"天翼没有 tatha"的认知不成立。
4. **天翼两个知识库均为空**：Looma（`looma-chromadb` / `looma_knowledge`）与 demopeter（`gfcc_chroma_data`）都只有 188KB 空 sqlite3；本地 demopeter 有 25242 向量。
5. **其余差异均为环境适配层**，不涉及代码：内核 LLM 天翼 stub vs 本地 ollama、天翼多 QCC 企查查、少 ollama 服务、`SIGNAL_BRIDGE_SECRET` 天翼为空、demopeter 天翼带认证、天翼有 redis/chroma 容器、无前端 vite。

---

## 1. 一致项

| 检查项 | 本地 ServBay | 天翼云端 | 说明 |
|---|---|---|---|
| 代码版本 | `feat/tianyi-central-chainb` `5fee72e` | 工作区 `d7d92db` · deploy `3962cd9`(v1.4.0) | ⚠️ 本地领先 14 commits；主环行为实测一致 |
| Looma 主环 | login→consent→ask 2.15s，intent=rag | 云端 2.06s，intent=rag | DeepSeek key 相同且双端实测可用 |
| LLM 首选 | deepseek | deepseek | 双端 `llm_configured: true` |
| 数据库 | SQLite `data/looma.db` | SQLite `data/looma.db` | `DATABASE_PATH` 一致 |
| 微信模式 | `WECHAT_DEV_MODE=true` | `WECHAT_DEV_MODE=true` | 双端均 dev 模式 |
| pgvector / postgres | 无 | 无 | 双端均未部署 |
| agentmemory | :3210 正常 | :3210 正常 | 双端在跑 |
| tatha | :5210 正常 | :5210 正常 | 双端在跑（见 §3） |
| gfcc 内核 | :5211 正常 | :5211 正常 | 双端在跑，`store: sqlite` |

---

## 2. 差异项与影响

| 差异项 | 本地 ServBay | 天翼云端 | 影响评估 |
|---|---|---|---|
| 内核 LLM 槽 | `llm: ollama`（已接） | `llm: stub`（未接） | ⚠️ 功能性：天翼内核 memory/llm 走 stub 响应；天翼无 ollama 服务（`OLLAMA_HOST=127.0.0.1:11434` 不可达） |
| LLM provider 拓扑 | deepseek ✅ + ollama ✅ + openai 未配 | deepseek ✅ + ollama ❌ + openai 占位 key（`your-ope...`） | ⚠️ 天翼实际仅 deepseek 可用 |
| `LLM_PROVIDER_ORDER` | `deepseek,ollama,openai` | `deepseek` | 天翼单 provider |
| `SIGNAL_BRIDGE_SECRET` | 64 字符（`824b3402...`） | **值为空** | ⚠️ Bridge 2/3（Looma↔DemoPPI personality beacon 签名）在天翼未启用 |
| `SIGNAL_INGEST_SECRET` | dev 值（`dev-signal-s...`，len=26） | 生产值（`d2e9138f...`） | 值不同，天翼为生产值 |
| QCC 企查查 | 未配置（`qcc_configured: false`） | `qcc_configured: true`（QCC_ENABLED + `QCC_AUTH_TOKEN`） | 天翼比本地**多**企查查能力 |
| redis | 无（:6379 未监听） | `looma-redis` 容器（Up 6 days） | 天翼 redis 缓存生效，本地走进程内/降级 |
| chroma 服务 | :8000 未起（Looma 知识库降级） | `looma-chromadb` 容器在跑（库空） | 行为等价（`sources:[]`），机制不同 |
| 知识库内容 | 本地 demopeter 25242 向量；本地 Looma 无 chroma | 天翼 Looma + demopeter **均空库** | 天翼检索 0 命中；本地 Looma 直接降级跳过 |
| demopeter 认证 | 无认证，`/api/stats` 直出 | 有 `ETHOS_AUTH_SECRET`，`/api/stats` → `missing token` | 天翼 demopeter 被认证保护 |
| PPI :3000 | 正常 | 根路径 404（`demoppi-web-1` 容器在，路由不同） | 不影响 Looma 主环 |
| 前端 vite dev | :5173 / :5174 / :5175 | 无 | 生产不跑 dev 前端，符合预期 |
| `GFCC_SIGNAL_INGEST_URL` | `http://127.0.0.1:5211/v1/signal-ingest` | `http://host.docker.internal:5211/v1/signal-ingest` | 天翼走 docker 宿主网关，地址形态不同、指向一致（5211） |

---

## 3. 服务清单对比

| 服务 | 本地端口 | 本地形态 | 天翼端口 | 天翼形态 |
|---|---|---|---|---|
| Looma backend | :5200 | venv `python run.py`（dev.sh） | :5203→5200 | `looma-backend` 容器 |
| gfcc 内核 | :5211 | launchd | :5211 | `/data/gfcc` uvicorn |
| tatha | :5210 | venv | :5210 | `gfcc-tatha-1` 容器（0.0.0.0:5210） |
| demopeter | :5220 | nohup venv | :5220 | `gfcc-demopeter-1` 容器 |
| agentmemory | :3210 | docker compose | :3210 | `gfcc-am-*` 4 容器 |
| PPI | :3000 | node | :3000 | `demoppi-web-1` 容器 |
| 前端 PlanetX/T-space/portal | :5173/:5174/:5175 | vite dev | — | 无 |
| ollama | :11434 | 本机服务 | — | 无 |
| redis | — | 无 | (容器内) | `looma-redis` |
| chroma | — | :8000 未起 | (容器内) | `looma-chromadb` + `gfcc-chroma-1` |
| nginx | api.servbay.host→5200 | ServBay | api.genz.ltd→5203 | nginx + Cloudflare |

---

## 4. 配置键对比（脱敏）

| 键 | 本地 | 天翼 |
|---|---|---|
| `DEEPSEEK_API_KEY` | `sk-1fc74...`（len=35）✅ 实测通 | 同值 ✅ 实测通（修复后） |
| `JWT_SECRET` | `dev-secr...`（len=31，dev 值） | `BTsWBfPz...`（生产值） |
| `SIGNAL_BRIDGE_SECRET` | `824b3402...`（len=64） | **空** |
| `SIGNAL_INGEST_SECRET` | `dev-signal-s...`（dev 值） | `d2e9138f...`（生产值） |
| `WECHAT_DEV_MODE` | `true` | `true` |
| `LLM_PROVIDER_ORDER` | `deepseek,ollama,openai` | `deepseek` |
| `QCC_ENABLED` | 未设置 | `true` |
| `GFCC_SIGNAL_INGEST_URL` | `http://127.0.0.1:5211/...` | `http://host.docker.internal:5211/...` |
| `DATABASE_PATH` | `./data/looma.db` | `data/looma.db` |
| `CHROMA_*` | 未设置（降级） | `localhost:8000` / `local` / `looma_knowledge` |
| `ETHOS_AUTH_SECRET`（demopeter） | 未设置（无认证） | 已设置（认证生效） |

> 注：天翼上 `OPENAI_API_KEY=your-ope...` 为占位符（`providers_configured.openai` 虽为 true 但不可用）；本地未设置 openai。

---

## 5. 结论

- 双端**非同一代码版本**（本地 `5fee72e` vs 天翼工作区 `d7d92db`、deploy 锚点 `3962cd9`，本地领先 14 commits），但 Looma 主环（认证/consent/ask/DeepSeek）行为实测一致；差异集中在 Supabase unified auth、LLM ops、weizuo-prep 等非主环路径。
- 用户前提"天翼没有 tatha、未灌数据"需修正：**天翼有 tatha**；天翼 Looma 与 demopeter **两个知识库均空**，而本地 demopeter 已灌 25242 向量（本地 Looma 本身也无知识库）。
- 其余差异均为**部署环境适配**（容器化 vs venv、生产密钥 vs dev 密钥、服务有无），不涉及业务逻辑与契约，不影响本机 ServBay 开发。
- 若 Windows 侧需对齐行为，注意天翼差异中最具功能性的是：内核 LLM=stub、`SIGNAL_BRIDGE_SECRET` 为空（信号桥签名未启用）、QCC 仅天翼可用、天翼知识库待灌数。

## 6. 后续建议（非阻塞）

1. 天翼知识库灌数（Looma `looma_knowledge` 与 demopeter `gfcc_chroma_data`）——对齐本地 demopeter 灌数流程。
2. 天翼 `SIGNAL_BRIDGE_SECRET` 若需启用 Bridge 2/3，需补与本地一致的密钥。
3. 天翼内核 LLM 若需从 stub 升级，需部署 ollama 并接线。
4. 本地 QCC 如需对齐天翼能力，补 `QCC_ENABLED`/`QCC_AUTH_TOKEN`。

---

## 7. 待 Windows 侧确认（交接件）

> 请按 §A 勾选事实确认，按 §B 填写处理意向，直接回复本文件即可。
> 事实依据：`check-consistency.sh` 2026-09-01 22:38 实测 + 双端 health/端口/.env 检查。

### A. 事实确认（请逐条打勾，有异议请注明）

- [ ] **A1 天翼有 tatha**：`gfcc-tatha-1` 容器在跑（0.0.0.0:5210），仅未被 nginx 代理——"天翼没有 tatha"不成立。
- [ ] **A2 天翼两个知识库均为空**：Looma（`looma_knowledge`）与 demopeter（`gfcc_chroma_data`）均 188KB 空 sqlite3；本地 demopeter 已灌 25242 向量（本地 Looma 本身也无库）。
- [ ] **A3 天翼代码版本**：工作区 `d7d92db`、deploy 锚点 `3962cd9`(v1.4.0)；本地 `5fee72e`，领先天翼工作区 14 commits——"双端同版本 5fee72e"不成立；主环行为仍实测一致。
- [ ] **A4 差异定性**：除 §2 差异项外均为部署环境适配（容器化 vs venv、生产/开发密钥、服务有无），不涉及业务契约。

### B. 功能差异处理意向（对 §6 逐项拍板）

| # | 事项 | 意向（做 / 不做 / 待定） | 负责人 | 期望时间 |
|---|---|---|---|---|
| B1 | 天翼知识库灌数（`looma_knowledge` + `gfcc_chroma_data`，对齐本地 demopeter 灌数流程） | | | |
| B2 | 天翼补 `SIGNAL_BRIDGE_SECRET`（启用 Bridge 2/3 信号桥签名，与本地一致） | | | |
| B3 | 天翼内核 LLM stub → ollama（部署 + 接线） | | | |
| B4 | 本地补 QCC（`QCC_ENABLED`/`QCC_AUTH_TOKEN`，对齐天翼） | | | |

### C. 版本锚点决策

- [ ] 同意打新发布锚点（建议 `v1.4.1`，本地 `5fee72e`），走治理手册 §2.2：打 tag → 推 gitee → 天翼 `checkout -B deploy v1.4.1` → 回归
- [ ] 暂不打，先处理 B 项
- [ ] 其他：__________

### D. 其他意见

________________________________________________

**回复人：__________  日期：__________**
