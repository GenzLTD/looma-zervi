# Tatha × planetx-tatha 闭环开发适配实施包（2026-10-05）

> 版本：v1.1（方案级，待评审，未实施；§十五为 2026-10-06 对照代码后的施工约束）
> 日期：2026-10-05
> 用途：项目成员评估能否参与、认领任务包、给出工时异议
> 口径：owner 拍板后，拉取请求分别进 `GenzLTD/Tatha` 与 `GenzLTD/planetx-tatha`。本文件只放在 looma-zervi `docs/` 作评审入口，不在本仓改运行时代码。

## 一、一句话

Tatha 负责能力证据与职位匹配，planetx-tatha 负责身份、证明和链上锚点。技能证据进去之后，必须带着 `yedall_attestation` 回来，匹配才把该技能标成「已验证」。

## 二、已核实现状（2026-10-05）

| 仓 | 主干 | 未合并请求 | 与闭环的关系 |
|---|---|---|---|
| [GenzLTD/Tatha](https://github.com/GenzLTD/Tatha) | `70455cb`（2026-09-05，Codespace） | [#2](https://github.com/GenzLTD/Tatha/pull/2) `feat/skill-evidence-ingest`（2026-10-01，+1195） | 摄入端已写好，证明回写还没有 |
| [GenzLTD/planetx-tatha](https://github.com/GenzLTD/planetx-tatha) | `195c8c0`（2026-09-30，MBTI 花语 16 型） | [#1](https://github.com/GenzLTD/planetx-tatha/pull/1) 依赖对齐；[#2](https://github.com/GenzLTD/planetx-tatha/pull/2) MBTI 三态 | 信任环是内存桩；性格契约在 #2 |

Tatha #2 已经落地、但未进主干的部分：

- `POST /v1/skills/ingest`：`X-Signature = HMAC-SHA256(SIGNAL_BRIDGE_SECRET, raw_body)`
- 幂等键 `(signal_type, user_id_hash, nonce)`
- 模型 `tatha.evidence.schemas.SkillProofPayload`，其中 `ProofItem.type` 已允许 `yedall_attestation`
- `resume_enhancer`：按 `user_id_hash` 把证据注入 `/v1/jobs/match`，失败不阻断匹配
- 存储：`.data/skills_evidence.db`（可用 `TATHA_EVIDENCE_DB` 覆盖）

planetx-tatha 主干上已有、但仍是桩的部分：

- `yeDall/tatha_trust/core/tatha/service.py` 的 `TathaService.invoke`：关键词抽技能，信任分写死 `[80, 85, 90]`，结果放内存字典
- `yeDall/tatha_trust/events/bus.py` 已定义事件：`tatha.invoke.accepted` / `tatha.invoke.completed` / `tatha.invoke.denied` / `trust.zkp.generated` / `trust.chain.anchored`
- `generate_zkp()`、`anchor_to_chain()` 已有函数，没有 HTTP 入口，也没有回调 Tatha

空着的半圈：摄入成功后没有人调用 planetx；`proofs[]` 里的 `yedall_attestation` 从未被写入；匹配端把「有证据」和「已锚点」当成同一件事。

## 三、目标回路

关联键只有一个：`user_id_hash = sha256(email.lower().trim())`，64 位 hex。邮箱与简历原文不出 Tatha。

```
Guibu / 调用方
  → Tatha  POST /v1/skills/ingest          验签、落库
  → Tatha  计算 payload 的 result_hash     只含哈希
  → planetx POST /v1/trust/attest          VC 校验 → ZKP → 锚点
  → 返回 proofs[]: { type: yedall_attestation, value: tx_id }
  → Tatha  把 proof 写回该条 evidence
  → Tatha  POST /v1/jobs/match             有锚点 = 已验证；无锚点 = 未验证
```

跨仓只允许这些字段：`user_id_hash`、`did`、`service_type`、`payload_hash`、`result_hash`、`vc_id`、`tx_id`、`statement_id`。禁止传递简历正文、excerpt、邮箱、技能原文。

## 四、本期范围

### 要做

| 编号 | 内容 | 仓 |
|---|---|---|
| P0 | 合入已开的 3 个拉取请求，作为后续分支的基线 | 两仓 |
| ID-1 | `user_id_hash ↔ DID` 绑定 | planetx-tatha |
| TR-1 | `TathaService` 改为调用 Tatha HTTP，去掉关键词打分 | planetx-tatha |
| AT-1 | `POST /v1/trust/attest`，发出已有信任事件并返回 proof | planetx-tatha |
| EV-1 | 摄入后回调 attest，把 proof 写回，匹配区分已验证 / 未验证 | Tatha |
| MB-1 | 性格分析只保留 planetx #2 的三态契约 | 两仓 |
| QA-1 | 跨仓冒烟脚本：摄入 → 锚点 → 匹配 | 两仓各一份调用说明 |

### 本期不做

- 不合并两个仓库，不把 YeDall 拷进 Tatha，也不把打分引擎留在 planetx
- 不改 Guibu 契约真源；`skill-proof.v1` 的 `proofs[].type` 已包含 `yedall_attestation`，本期只填值
- 不改 looma-zervi 的产品打分与人格 beacon。planetx #2 已说明产品面仍是 looma 那份旧分析器，那是后续包
- 不上主网。锚点沿用 `ChainAnchor` 现有实现（本地 / 测试链）
- 不做花语补位策略。`partial` 继续返回「待分析」，与 planetx #2 的已知行为变更一致

## 五、接口（实现时按此冻结）

### 5.1 身份绑定（planetx-tatha 新增）

```
POST /v1/identity/bind
```

```json
{
  "user_id_hash": "<64 hex>",
  "did": "did:web:tatha.io:users:<local-id>"
}
```

- 同一 `user_id_hash` 重复绑定返回已有 `did`（幂等）
- 存储表 `identity_bind(user_id_hash PRIMARY KEY, did, created_at)`，SQLite，路径由 `YEDALL_BIND_DB` 指定
- 响应 `200 { "did": "...", "status": "bound" | "exists" }`
- 未绑定就调用 attest → `409 { "code": "identity_unbound" }`

### 5.2 证明（planetx-tatha 新增，Tatha 来调）

```
POST /v1/trust/attest
X-Signature: HMAC-SHA256(YEDALL_ATTEST_SECRET, raw_body)
```

```json
{
  "user_id_hash": "<64 hex>",
  "service_type": "skill_assessment",
  "payload_hash": "<sha256 canonical json>",
  "result_hash": "<sha256 canonical json>",
  "statement_id": "threshold_ge_70_v1"
}
```

处理顺序（全部走现有类，不新写密码学）：

1. 验签失败 → `401 invalid_signature`
2. `identity_bind` 查不到 → `409 identity_unbound`
3. `TrustEngine.assess`：VC 无效或决策 `deny` → `200 { "status": "denied" }`，并发 `tatha.invoke.denied`。Tatha 不把此条标为已验证
4. 通过 → `ZKPProver.generate_threshold_proof` → `ChainAnchor.anchor`
5. 成功响应：

```json
{
  "status": "anchored",
  "vc_id": "vc:…",
  "tx_id": "tx:…",
  "statement_id": "threshold_ge_70_v1",
  "proof": { "type": "yedall_attestation", "value": "tx:…" }
}
```

同时发布（载荷只含哈希与 id）：`tatha.invoke.completed`、`trust.zkp.generated`、`trust.chain.anchored`。

`service_type` 首期只接受 `skill_assessment`。`resume_parse` / `job_matching` 留在 `TathaService` 的计价表里，本期不开放。

### 5.3 Tatha 侧回写

摄入 `status=stored` 之后（`duplicate` 不重复锚点）：

1. `result_hash = sha256(canonical_json(payload))`，算法与 planetx `HashCalculator` 对齐，单测用固定向量锁死
2. `YEDALL_ATTEST_URL` 未设置 → 跳过，证据保持未验证，匹配仍可用（与现在「增强失败不阻断」一致）
3. 设置了 → `POST /v1/trust/attest`。超时 3s，失败记日志，不让摄入接口 5xx
4. `status=anchored` → 把返回的 `proof` 追加进该行 `payload.proofs` 并更新 SQLite
5. `resume_enhancer` 拆两列文本：
   - 已验证：`proofs` 中存在 `type=yedall_attestation`
   - 未验证：有证据、无该 type

`/v1/jobs/match` 在已有 `verified_skills` 旁增加 `attested_skills`。旧字段保留，调用方未升级时行为不变。

## 六、任务包（可认领）

认领人在文末表格填名字。一个包一人，QA-1 可与 EV-1 同一人。

### P0 基线合入（评审人，0.5 天）

先合再开新分支。新工作基于合入后的主干，不基于今天的开放分支叠提交。

| 请求 | 合入前核对 |
|---|---|
| Tatha #2 | `tests/test_evidence.py` 通过；`REQUIRE_SIGNAL_HMAC=true` 且密钥为空时进程拒绝启动 |
| planetx #1 | 按 `requirements.txt` 裸装后 `GET /health` 为 200。接受镜像变大（torch 间接依赖，PR 正文已写明） |
| planetx #2 | `pytest tests/ --ignore=tests/e2e` 为 46 passed。消费方按 `status` 判断，不能只看 `mbti_type != XXXX` |

### ID-1 身份绑定（planetx 后端，1 天）

| 编号 | 任务 | 落点 |
|---|---|---|
| ID-1.1 | `POST /v1/identity/bind` + SQLite | `yeDall/tatha_trust/api/app.py` 新增路由；新文件 `yeDall/tatha_trust/core/identity/bind.py` |
| ID-1.2 | 单测：首次 bound、重复 exists、哈希非 64 hex 则 422 | `yeDall/tatha_trust` 下新测试，或仓内 `tests/` 中与 trust 相邻的文件 |

验收：同一哈希绑定两次，`did` 不变；库中无邮箱列。

### TR-1 打分只走 Tatha（planetx 后端，1.5 天）

| 编号 | 任务 | 落点 |
|---|---|---|
| TR-1.1 | `TathaService._ai_parse_resume` 改为 HTTP 客户端 | `yeDall/tatha_trust/core/tatha/service.py` |
| TR-1.2 | 客户端只请求 Tatha 已有接口，默认 `TATHA_API_BASE`（本地 `http://127.0.0.1:8010`） | 新文件 `yeDall/tatha_trust/core/tatha/remote.py` |
| TR-1.3 | 关键词技能表与写死的 `recent_scores=[80,85,90]` 从 `invoke` 路径删除 | 同上 service.py |
| TR-1.4 | `invoke` 仍先 `TrustEngine.assess`，`deny` 不发 HTTP | 保持现有分支 |

验收：对桩 HTTP 返回固定 JSON 时，`TathaResult.result_hash` 非空，且源码中不再出现学校关键词表。Tatha 宕机时 `invoke` 返回 `status=error`，不回退到本地打分。

### AT-1 证明端点（planetx 后端，1.5 天）

| 编号 | 任务 | 落点 |
|---|---|---|
| AT-1.1 | `POST /v1/trust/attest` 按 §5.2 实现 | `yeDall/tatha_trust/api/app.py` |
| AT-1.2 | 复用 `generate_zkp`、`anchor_to_chain`、`EventBus` | `service.py`、`events/bus.py` |
| AT-1.3 | 密钥 `YEDALL_ATTEST_SECRET`；未配置时端点 503，避免免签进进程 | 与 Tatha `assert_signal_bridge_ready` 同一模式 |
| AT-1.4 | 单测：未绑定 409、坏签名 401、deny 不产生 tx、成功体含 `proof.type=yedall_attestation` | 新测试文件 |

验收：成功路径的事件日志里能按顺序找到 `tatha.invoke.completed` 与 `trust.chain.anchored`。事件 payload 用夹具断言不含 `excerpt` 与 `@`。

### EV-1 证据回写（Tatha 后端，1.5 天）

依赖：P0 的 Tatha #2 已进主干；AT-1 的请求/响应样例已冻结（可先用桩）。

| 编号 | 任务 | 落点 |
|---|---|---|
| EV-1.1 | 摄入成功后的 attest 客户端，失败不 5xx | `src/tatha/evidence/` 新 `attest_client.py`；在 ingest 路由调用 |
| EV-1.2 | 锚点成功则更新该行 `payload.proofs` | `src/tatha/evidence/store.py` |
| EV-1.3 | `resume_enhancer` 拆已验证 / 未验证；响应增加 `attested_skills` | `src/tatha/evidence/resume_enhancer.py`、`src/tatha/api/app.py` |
| EV-1.4 | 固定向量：同一 payload 的 `result_hash` 与 planetx `HashCalculator` 一致 | `tests/test_evidence.py` 加一条 |

验收：

- 桩 attest 返回 anchored → 库中该行 `proofs[0].type == yedall_attestation`
- 桩超时 → 摄入仍 200 `stored`，`attested_skills` 为空，`verified_skills` 仍在
- `YEDALL_ATTEST_URL` 空 → 与今天 #2 的行为一致

### MB-1 性格契约收成一份（Tatha 后端，1 天）

依赖：planetx #2 已进主干。

| 编号 | 任务 | 落点 |
|---|---|---|
| MB-1.1 | 以 planetx 合入后的 `src/tatha/agents/mbti_analyzer.py` 与 `central_brain.py` 分流规则为真源，覆盖 Tatha 仓内同路径文件 | Tatha `src/tatha/agents/mbti_analyzer.py`、`src/tatha/api/central_brain.py` |
| MB-1.2 | 把 planetx #2 的 17 条契约测试带进 Tatha | Tatha `tests/test_mbti_analyzer.py` |
| MB-1.3 | 在 Tatha README 或 `docs/MBTI本地资产与适配建议.md` 加 5 行：三态含义、花语只在 `status=ok` | 文档 |

验收：零关键词文本不得返回 `INFP` + 置信 50。Tatha 与 planetx 两份分析器对同一夹具的 `status` / `mbti_type` 一致。本期用复制加夹具锁，不新建共享包（见评审项 4）。

### QA-1 跨仓冒烟（QA 或任一后端，1 天）

| 编号 | 任务 | 落点 |
|---|---|---|
| QA-1.1 | 脚本：bind → ingest → 断言 proof 已回写 → match 的 `attested_skills` 含该技能 | Tatha `scripts/eval_skill_proof.py` 增加可选 `--attest`；planetx 侧用现有 demo 进程 |
| QA-1.2 | 负例：错误 HMAC、未绑定、attest 超时 | 同一脚本的三个子命令或三个断言 |

验收命令（本地两进程）：

```bash
# 终端 A：planetx-tatha 信任 API（端口在 AT-1 实现时写入 README，建议 8020）
# 终端 B：Tatha
uv run uvicorn tatha.api.app:app --host 127.0.0.1 --port 8010

YEDALL_ATTEST_URL=http://127.0.0.1:8020 \
YEDALL_ATTEST_SECRET=dev-attest \
SIGNAL_BRIDGE_SECRET=dev-bridge \
  uv run python scripts/eval_skill_proof.py --attest
```

退出码沿用现脚本：`0` 通过，`1` 失败，`2` 跳过（缺 LLM 时匹配段跳过，证明回写段仍须通过）。

## 七、依赖与并行

```
P0（三个已开请求合入）
 ├─ ID-1 身份绑定
 │    └─ AT-1 证明端点
 │         └─ EV-1 回写（可先对桩开发，最后对 AT-1 联调）
 ├─ TR-1 远程打分（与 ID-1 并行，不阻塞 EV-1）
 └─ MB-1 性格契约（与信任环并行，只依赖 planetx #2）
QA-1 在 EV-1 接口冻结后开始，与 EV-1 收尾并行
```

人员安排：planetx 一人串 ID-1 → AT-1；另一人做 TR-1。Tatha 一人等 P0 后做 EV-1，MB-1 可由同一人或第三人做。QA-1 约 1 人日，放在最后两天。

合计约 8 人日。两人并行时日历时间约 4 天（含 P0 评审）。

## 八、环境变量（新增）

| 变量 | 仓 | 缺省行为 |
|---|---|---|
| `YEDALL_ATTEST_URL` | Tatha | 空则不回调，证据保持未验证 |
| `YEDALL_ATTEST_SECRET` | 两边相同 | planetx 未配置则 attest 返回 503 |
| `YEDALL_BIND_DB` | planetx | 默认 `yeDall/tatha_trust/.data/bind.db`，目录 gitignore |
| `TATHA_API_BASE` | planetx | 默认 `http://127.0.0.1:8010` |

已有、本期继续用：`SIGNAL_BRIDGE_SECRET`、`REQUIRE_SIGNAL_HMAC`、`TATHA_EVIDENCE_DB`。

## 九、验收总表（owner 拍板用）

| 项 | 通过判据 |
|---|---|
| P0 | 三个请求在各自主干，CI 或 PR 描述中的测试数成立 |
| 身份 | 绑定表只有哈希与 DID |
| 证明 | 未绑定 409；坏签名 401；成功体的 `proof.type` 为 `yedall_attestation` |
| 回写 | 锚点成功后 SQLite 行内有该 proof；attest 宕机时摄入仍 200 |
| 匹配 | 同一简历：无锚点不出现在 `attested_skills`；有锚点出现 |
| 打分单源 | planetx `invoke` 不再本地关键词打分 |
| 性格单源 | 零信号夹具在两仓结果一致，且不是 `INFP`/50 |
| 隐私 | attest 请求夹具与事件日志中无 excerpt、无邮箱 |

## 十、风险

| 风险 | 等级 | 处理 |
|---|---|---|
| `HashCalculator` 与 Tatha 侧 canonical JSON 键序不一致，锚点对不上 | 高 | EV-1.4 用一条固定向量在两仓各断言一次；不一致时以 planetx `HashCalculator.hash_result` 为准改 Tatha |
| 成员基于未合入分支继续开发，和 #2 的 CORS / 门禁再冲突 | 高 | P0 完成前不开工 EV-1 / MB-1 |
| attest 失败被吃掉，调用方以为已验证 | 中 | 响应字段分开：`verified_skills` 与 `attested_skills`。文档与脚本都断言「超时 ≠ 已验证」 |
| planetx #1 把 torch 打进镜像 | 中 | 接受 PR 正文里的体积说明；本期不改 Dockerfile |
| planetx #2 的 `partial` 不再给花语，下游若把 flower 当必填会空 | 中 | MB-1 文档写明；本期不改花语策略 |
| 事件总线仍是内存，进程重启丢日志 | 低 | 证明以 SQLite 中的 `proofs` 与链上 `tx_id` 为准，不以内存事件为准 |
| 有人把简历正文放进 attest body | 高 | 评审代码时拒绝多出来的字段；Pydantic `extra=forbid` |

## 十一、评审项（owner 勾选）

1. 是否批准按本包开拉取请求？（Y/N）
2. 工时（P0 0.5 + ID-1 1 + TR-1 1.5 + AT-1 1.5 + EV-1 1.5 + MB-1 1 + QA-1 1）是否接受？（Y/N；N 请改数字）
3. 跨仓密钥是否同意用共享 `YEDALL_ATTEST_SECRET`，与 Guibu 的 `SIGNAL_BRIDGE_SECRET` 分开？（Y/N）
4. 性格分析本期用「复制 planetx 文件 + 夹具锁」，不新建公共包？（Y/N；若 N，MB-1 改期，不阻塞信任环）
5. attest 失败时摄入仍返回 200，仅不打已验证标记？（Y/N；建议 Y）
6. `service_type` 首期只有 `skill_assessment`？（Y/N）
7. looma 产品面的分析器移植是否确认放到下一包？（Y/N；建议 Y）
8. 锚点是否确认停留在现有 `ChainAnchor` 测试实现，本期不上主网？（Y/N）

## 十二、成员认领

在对应行写下 GitHub 登录名与可开始日期。一人可领相邻的两个包（ID-1+AT-1，或 EV-1+QA-1）。P0 由评审人执行，不占开发认领。

| 包 | 仓 | 人日 | 前置 | 认领人 | 可开始 |
|---|---|---|---|---|---|
| ID-1 身份绑定 | planetx-tatha | 1 | P0 | | |
| TR-1 远程打分 | planetx-tatha | 1.5 | P0 | | |
| AT-1 证明端点 | planetx-tatha | 1.5 | ID-1 | | |
| EV-1 证据回写 | Tatha | 1.5 | P0；联调需 AT-1 | | |
| MB-1 性格契约 | Tatha | 1 | planetx #2 合入 | | |
| QA-1 跨仓冒烟 | 两仓 | 1 | EV-1 接口冻结 | | |

认领前请自测：能克隆对应私有仓、能在本地把该仓现有测试跑起来。跑不起来的人先协助 P0 评审，不领 ID-1 / EV-1。

## 十三、建议日历

```
Day 0   评审 §十一；认领 §十二
Day 1   P0 合入。planetx 开工 ID-1 与 TR-1。Tatha 读 #2 已合入代码，准备 EV-1 桩
Day 2   AT-1 开工。MB-1 开工。EV-1 对桩写回写与测试
Day 3   AT-1 与 EV-1 联调。QA-1 脚本
Day 4   按 §九 验收。两个仓各一个拉取请求（planetx：ID-1+TR-1+AT-1；Tatha：EV-1+MB-1）
```

## 十四、反馈方式

回复两件事即可开工：

1. §十一 的 8 个 Y/N
2. §十二 认领表（登录名 + 日期）

未拍板前不要往两个仓推闭环功能分支。P0 的三个已开请求可以并行评审。

## 十五、可行性核对（2026-10-06）

对照 `GenzLTD/Tatha` `70455cb`、`GenzLTD/planetx-tatha` `195c8c0`，以及当时仍开放且可合并的 Tatha #2、planetx #1、planetx #2。回路方向成立，按 v1.0 原文直接写代码会在现有实现上对不上。认领前先按下面五条改施工，再动 ID-1 / AT-1 / EV-1。

1. **不要调用现成的** `POST /v1/chain/anchor` **和** `POST /v1/zkp/prove`。`ChainAnchor.anchor` 只收一个 `ChainTransaction`；HTTP 层传的是 `data` / `data_hash` / `sender_did`。`ZKPProver.generate_threshold_proof` 的参数是 `request_id` 与 `score`；HTTP 层传的是 `entity_did` 与 `value`。这两条路由按现在的调用会 `TypeError`。AT-1 应直接组装 `ChainTransaction`，再调用 `anchor(tx)`。信任服务文件是 `yeDall/tatha_trust/api/app.py`，默认端口已是 8020，新路由 `/v1/identity/bind` 与 `/v1/trust/attest` 跟现有路径不冲突。

2. **`threshold_ge_70_v1` 证明的是「分数 ≥ 70」。** 技能证据没有这个分数，attest 请求体也不带简历或摘录。`skill_assessment` 只锚 `payload_hash` / `result_hash`。阈值证明留给已有 `consensus_score` 的简历解析。

3. **VC 无效不会得到 v1.0 写的 `deny`。** `TrustEngine.assess` 在 `vc_valid=false`、其余用默认值时总分约 63，决策是 `confirm`（通过线 75，拒绝线低于 60）。验收要按这个引擎写，不能假设无效 VC 会拒绝且不产生 tx。

4. **锚点重启后无法复核。** `ChainAnchor` 是内存哈希链，DID / VC 也在进程内存里。Tatha SQLite 能记下 `tx_id`，planetx-tatha 进程重启后链上对不上。本期是同一次进程内的演示，不是可复核的链上凭证。

5. **第一次锚点超时后要能补试。** v1.0 规定 `duplicate` 不再锚点。摄入已 `stored`、证明没写上时，这条证据会一直停在未验证。无 `yedall_attestation` 的重复请求应再请求一次 attest。

哈希公式：`HashCalculator.hash_result` 哈希的是带 `status` 的结果对象，`hash_payload` 还可以用 `request_id` 加盐。技能回路由 Tatha 算好哈希再送出，planetx-tatha 只保存，不必两边重算。

TR-1 与技能回路无关。`TathaService.invoke` 仍要简历正文，不要接到 `/v1/trust/attest`。MB-1 可以单独做。
