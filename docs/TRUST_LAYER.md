# 信任层：短暂交集 → 长期记忆体 → 信任凭证

> **版本：** 1.0 · **日期：** 2026-07-14  
> **状态：** 产品信念 + 契约真源（非竞品模仿路线）  
> **机器可读：** [trust.v1.json](../backend/contracts/trust.v1.json)  
> **关联：** [identity.v1.json](../backend/contracts/identity.v1.json) · [ZERVI_GENZER_IMPLEMENTATION.md](./ZERVI_GENZER_IMPLEMENTATION.md)

---

## 0. 核心命题（Jason 裁定）

人与人的相处，建立在**社会化交集里的短暂记忆**上：

- 一起做完人格测试的那十几分钟  
- 舰队里共闯一关的共在感  
- 一次 match 扫描、一句确认  
- 一段 Ask 对话、一次分享触达  
- 合伙人第一次点开某位候选人的瞬间  

这些在生物学和社会学上本是**短暂的**——见面结束，印象模糊，难以被第三方验证。

**我们要做的：** 把这些短暂交集**长期记忆体化**，形成可审计、可回放、可被智能体检验的**信任验证凭证**——而不是把 LinkedIn 好友数、六度路径长度或竞品式「内推计数」当成信任。

```text
短暂交集（Ephemeral Encounter）
        ↓ 捕获
长期记忆体（Memory Record）     ← append-only，含 text / dialogue / behavior
        ↓ 分析
Trust Agent / 规则引擎
        ↓ 输出
信任凭证（Attestation on Claim） ← verified / weak / disputed …
        ↓ 呈现
identity 公开档案 / 合伙人信用摘要
```

---

## 1. 我们刻意不做的（竞品路线）

| 竞品常见做法 | 我们的立场 |
|-------------|------------|
| 链接越多越可信 | **无证明**；结构可达 ≠ 信任 |
| 会员/实名即信任 | 身份门槛 ≠ 行为验证 |
| 扩图 KPI、Hub 增长 | 图几何仅作**关系上下文** |
| 静态 CV + AI 复述 | 信任来自**交集记忆体**，非 PDF |
| 模仿 Refer/脉脉 UI | 体验可参考，**信任本体不同** |

---

## 2. 三层模型

| 层 | 名称 | 回答的问题 |
|----|------|------------|
| **几何层（弱）** | social reachability | A 与 B 结构上是否曾通过某条人际链相连？ |
| **记忆层（强）** | trust memories | 交集当时发生了什么（文字/对话/行为）？ |
| **凭证层（强）** | attestation | 智能体能否用记忆体支撑某个 identity claim？ |

`six_degrees` 实验室与 `/v1/social/*` 只属于**几何层**；用户可见的「信用」必须来自**记忆层 + 凭证层**。

---

## 3. 交集类型 → 记忆体（映射表）

| 交集 | 短暂性 | 记忆体化 |
|------|--------|----------|
| 人格测评完成 | 结果页一闪 | `personality_completion` + 文本快照 |
| 舰队共在 | 同舰闯关时段 | `fleet_co_presence` |
| match 扫描 | 一次动画与分数 | `match_scan` |
| 双向共识确认 | 双方点头的瞬间 | `consensus_exchange` → **可升格为 verified 凭证** |
| Ask / 合伙人对话 | 多轮上下文 | `dialogue_session`（长期保留策略见契约） |
| 分享/推荐 | 传播触达 | `share_signal` / `referral_binding` |
| 合伙人撮合接触 | 查看/导入候选人 | `partner_candidate_contact` |

详见 `trust.v1.json#intersection`。

---

## 4. 三类证据通道

| 通道 | 长期跟踪什么 | Agent 验证什么 |
|------|-------------|----------------|
| **文字** | 自称、发布文案、公开档案 | 与行为是否矛盾、承诺是否兑现 |
| **对话** | Ask、确认话术、撮合沟通 | 共识是否真实、是否回避关键确认 |
| **行为** | mission、consensus 状态、spread 事件 | 时序是否自洽、是否存在刷量 |

**不是**「点一次 +5 分」，而是**事件链是否支撑 claim**。

---

## 5. 与 identity / game 契约的关系

```text
identity.v1.json     「我是谁」— claims 列表
game.v1.json         「我做过什么闯关」— 产生 behavior 交集
trust.v1.json        「这些交集是否足以验证 claim」— attestation
payment.v1.json      「我付了什么档」— 商业，不替代信任
```

示例：

- claim `match_mission` 仅在 attestation=`verified` 且 evidence 含 `consensus_exchange` 记忆体时，对外展示「验证组队成功」。  
- 仅有「1 度人脉」**不能**自动 verified 任何 claim。

---

## 6. 智能体路线

| 阶段 | 做法 |
|------|------|
| **v0** | 规则：consensus verified → match claim verified；人格 sync → weak |
| **v1** | Trust Agent 读 memory stream：一致性、对话互惠、行为矛盾 |
| **v2** | 可训练模型 + 人工抽检；Genzer 终端信号作**补充 evidence**，非真源 |

训练数据来自**已标注的记忆体**，不是来自竞品公开数据或纯图拓扑。

> **工程可替换性（职位匹配 ≠ Trust v2，但同构端口）：** 见 [INFERENCE_MATCH_SCORER_REPLACEABILITY.md](./INFERENCE_MATCH_SCORER_REPLACEABILITY.md)。Trust 评分端口登记为该文件 M4，不阻塞匹配 M0–M3。

---

## 7. 工程 P0（认可修正后的优先序）

1. 定稿 `trust.v1.json` ✅  
2. `match_consensus` + `trust_memories` + `trust_attestations` 表 ✅  
3. `POST /v1/game/match/acknowledge` → `consensus_exchange` 记忆体 + `match_mission` rule attestation ✅  
4. `POST /v1/game/mission-complete`（match）门控：须 verified attestation ✅  
5. `GET /v1/trust/memories` · `GET /v1/trust/claims/<claim_key>` ✅  
6. **废弃**用户可见的 `trust_score(degrees)` 语义；social API 仅返回 reachability — 待办  
7. 合伙人档案 UI：展示 **attestation 摘要** — 待办  

**测试：** `pytest backend/tests/test_trust.py -v`

---

## 8. 一句话

竞品优化的是**找到人**；我们记忆化的是**交集本身**，并用智能体把记忆变成**可验证的信任凭证**——这是社会化短暂记忆的产品化，不是社交图谱的放大版。

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-07-14 | 短暂交集记忆体化命题 + trust.v1 对齐 |
