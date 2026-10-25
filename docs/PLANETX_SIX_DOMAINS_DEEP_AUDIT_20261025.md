# PlanetX「六域」深度调研 · 设计初心与落地断层

> 2026-10-25 · Mac 侧实测（git 考古 + 逐行读源码 + SQLite 实读数，无转述）
> 范围：`~/Projects/PlanetX`、`~/Projects/looma-zervi`、`~/Projects/Vultr-Genzltd`
> 回答一个问题：**六域的设计初衷是什么，今天到底落地了多少，哪一段只停在页面上。**

---

## 〇、一句话结论

**设计初心非常锋利，而且被完整写下来了 —— 但那份文档在实现落地的第二天就被当成垃圾删掉了。**
今天代码里有一套**质量相当高**的六域引擎（30 格交互矩阵、手写18选项、5 张表、16 个接口），
也有三套各自转的前端，但三者**互不相连**：

> **核心机制「价值印记」在全代码范围内不可达 —— 数据库里是 0 行。**
> 它一旦是 0，跨域回声、涌现策略、终极清算全部连带失效。
> 所以今天的六域 = **内容全部在线，重量为零**。玩家做完选择，屏幕上会出现"你获得了「务实」印记"，
> 但没有任何一个比特记录过这件事。

---

## 一、设计初心：我把被删的 GDD 挖回来了

`domain_engine.py` 第 11 行写着 `Ref: PlanetX-T空间_游戏化预演设计_GDD.md §3.2/§7.1`，
但这份文档在工作区**不存在**（全机搜寻无命中）。

从 git 历史里恢复了它：

| 项 | 事实 |
|---|---|
| 原始路径 | `looma-zervi/reports/游戏化内测设计方案/PlanetX-T空间_游戏化预演设计_GDD.md` |
| 体量 | **872 行 / 54.9 KB** |
| 最后修改 | 2026-07-01 02:31，随 `3361011`「feat: Act1叙事状态机、跨域路径、DB持久化 — MVP内测就绪」一起提交 |
| **删除时间** | **2026-07-02 23:02**，`14e6287`「chore: 清理旧文档和报告，新增 pyproject.toml / uv.lock」 |
| 删除规模 | 该提交删了 **24 个文件 / 8024 行**，含 `tspace_act1_prototype.html`(1210行)、架构决策、竞品 BP 等 |
| 现存副本 | ❌ 工作区无 ❌ Vultr-Genzltd 无 → **唯一副本在 looma-zervi 的 git 历史里** |

> 已恢复归档 → `PlanetX-GDD-游戏化预演设计（从git历史恢复）.md`（本目录）

### 1.1 主题北极星（GDD §1.1）

> **在生存与意义之间，你如何选择？而当你选择之后，你还是你自己吗？**

GDD 明确写了这条北极星不是口号，而是检验标准：**每个机制、每段对话、每个数值都必须回答"这个设计是否在逼迫玩家面对生存 vs 意义的张力"。**

### 1.2 五大设计支柱（GDD §1.2）

| # | 支柱 | 承诺 | 检验问题 |
|---|---|---|---|
| P1 | **选择有重量** | 每个选择有可感知、可追溯的后果 | "删掉这个选择，玩家会注意到缺失吗？" |
| P2 | **系统诚于局限** | Navigator 的"不确定"是戏剧素材，不是技术缺陷 | "这个失败回退是在隐藏缺陷还是制造戏剧？" |
| P3 | **价值排序而非数值优化** | "钱多事少离家近"是排序题不是选分题 | "玩家在算数学还是在做取舍？" |
| P4 | **手工核心，AI 纹理** | 关键路径全部手写，AI 只做环境碎片 | "这段对话是作者意图还是 AI 生辰？" |
| **P5** | **六域一问** | **六个端口不是六条平行线，是六个价值取向；终点可收敛但路径必须有质感差异** | "走了不同域的玩家，对同一收敛点的理解是否不同？" |

P5 就是「六域」这四个字的真正定义 —— **六域不是六个功能页，是六个面朝同一问题的不同站位。**

### 1.3 三条价值轴 = "钱多事少离家近"（GDD §3.2）

| 轴 | 俗话 | 主要供能域 |
|---|---|---|
| survival 生存 | **钱多** | 职业域、信任域 |
| freedom 自由 | **事少** | 诗域、自我域 |
| belonging 归属 | **离家近** | 身份域、迷雾域 |

### 1.4 五套核心机制（GDD §3）

| 机制 | 一句话 | 关键数值 |
|---|---|---|
| 意图分发 Intent Dispatch | confidence 不是隐藏参数，是 Navigator 的**情绪状态**，对玩家完全可见 | 显示阈值 0.4 |
| **价值印记 Value Imprint** | 选择累积三轴点数，**不可见于 UI**，直到 Act 5 清算 | 每次选择 2 点（区间 1–5） |
| **跨域回声 Cross-Domain Echo** | 单轴 ≥8 点 → 在别的域触发角色/环境/系统/Navigator 回声 | 单轴阈值 8、每会话上限 2、域对冷却 2 会话 |
| Navigator 记忆 | 把 "X will remember that" 做成**真记忆**（表层/深层/碎片/禁忌四层） | 深层间隔 2 会话、碎片泄露 15%/会话 |
| 终级清算 The Reckoning | Act 5 三难困境，5 种结局（含隐藏的平衡者/拒绝者） | 解锁条件 总印记 ≥30 |

### 1.5 6×6 交互矩阵（GDD §7.1）

30 个有序对，三档：✅ 意图内 / ⚠️ 可接受 / 🚫 禁止。
**唯一两格 🚫：`信任域→迷雾域`（迷雾域无信任记录）与 `迷雾域→信任域`（信任系统失效）** —— GDD 强调"这不是 Bug，这是叙事"，但数值溢出才是 Bug。

### 1.6 五幕长期循环（GDD §2.4）

Act1 登陆 → Act2 漫游（解锁全部 6 域 + 首回声）→ Act3 深潜 → Act4 迷雾（Navigator 首次说谎）→ Act5 清算。
**今天只存在 Act 1。**

---

## 二、落地账：真实存在的资产（这部分是真心做出来了）

### 2.1 后端引擎（looma-zervi/backend）

| 文件 | 行数 | 内容 |
|---|---|---|
| `src/agents/domain_engine.py` | ~640 | 30 格 `INTERACTION_MATRIX`、`EchoType`、`EmergentStrategy`、**`class Tuning` 数值与 GDD §4.3 逐条对齐**（IMPRINT_PER_CHOICE_BASE=2 / MIN1 / MAX5 / ECHO_THRESHOLD_SINGLE_AXIS=8 / ECHO_PER_SESSION_MAX=2 / ECHO_COOLDOWN_SESSIONS=2） |
| `src/agents/act1_state_machine.py` | 493 | Act1 七步状态机，单域 0–6 步 / 跨域 0–10 步，含防傻保护（step 7→8 必须先有 cross_chosen） |
| `src/agents/narrative_content.py` | 657 | **手写内容**：6 域 × (1 遭遇 + 3 选择)，每选项带 `imprint_name/axis/points`；`POETRY_CROSS_CONTENT` 3 变体 × 3 选择；`NAVIGATOR_LINES` 6 句；6 份 `convergence` 质感（含 `truth_distance`） |
| `src/agents/convergence.py` | 620 | 收敛编排 + system prompt 组装 |
| `src/agents/navigator_memory.py` | 379 | 四层记忆 + DB 持久化 |
| `src/api/routes/narrative_routes.py` | 641 | **16 个端点** |
| `src/db/manager.py` | — | 7 张表：`narrative_sessions/events/feedback`、`act1_sessions`、`value_imprints`、`navigator_memories`、`domain_visits`、`emergent_strategy_log` |

内容质量是过硬的 —— 比如诗域第三选项「不补完。残缺的就是完整的。」，Navigator 回：
> 「……你是第一个不补完它的人。」

这是 **P4 手工核心** 的实证，不是 AI 生成的填充。

### 2.2 前端：三条各自转的实现

| # | 实现 | 位置 | 谁在用 | 后端依赖 |
|---|---|---|---|---|
| A | **静态单页原型** | `PlanetX/narrative.html`（25.5KB） | **外部用户实际可达**（`index.html:639` 的「🪐 进入 T 空间」按钮指向它） | `POST api.genz.ltd/v1/ask`，带 `navigator_mode:true` |
| B | **React 正式 app** | `looma-zervi/frontend/packages/planetx`，路由 `/tspace` | dev 环境 | `/v1/narrative/start` + `/engine/act1/{init,advance,choice,reset,content}` |
| C | **后端 DomainEngine** | 上面那套 | ❌ 无人调用 | 只有 `/engine/domain-enter` + `/engine/choice` 能触发印记/回声/涌现 |

**B 与 C 之间没有连线。** `TspaceNavigatorScreen.tsx` 699 行里，一次都没有请求 `/engine/domain-enter`、 `/engine/choice`、`/engine/state`。
而 `shared-core/src/api/createApi.ts:570-601` 里其实已经写好了 `NARRATIVE_EVENT / NARRATIVE_END / NARRATIVE_FEEDBACK / ACT1_STATE` 的客户端方法 —— **没有任何界面调用它们**。

---

## 三、🔴 六条断层（每条都有代码/数据证据）

### 断层 1：存在两组「六域」，只有 1 个域是同一个

| 来源 | 六域 | 证据 |
|---|---|---|
| **GDD + 叙事引擎**（设计初心） | 职业域 · 身份域 · **诗域** · **信任域** · **自我域** · **迷雾域** | `domain_engine.py:27`、`narrative_routes.py:21` |
| **RAG 知识库 + 意图路由**（后来的产品口径） | 职业域 · **学习域** · **生活域** · **社交域** · **健康域** · **创意域** | `central_brain.py:40`、`seed_knowledge.py:38-93` |

**交集只有「职业域」一个。** 其余 5 个完全不同。

连类型注释都自相矛盾：
```ts
// shared-core/src/types/narrative.ts:9
/** Valid narrative domains (六域 + 迷雾域) */   ← 意为 6+1=7
  | "职业域" | "诗域" | "自我域" | "身份域" | "信任域" | "迷雾域"  ← 实际 6 个，且已含迷雾域
```

**后果（连锁致命）**：用户说「我想探索六域」→ 命中 `KEYWORD_INTENTS["rag"]`（六域关键词就在 rag 词表里）→ 走**知识库问答**；
而叙事引擎的开关是 `central_brain.py:557 if context.get("navigator_mode") and intent == "unknown"` ——
**在普通对话里，intent 永远不是 unknown，六域引擎的门打不开。**

> 用户嘴里的六域 ≠ 系统实现的六域，而且入口还被 keyword 路由抢走了。

### 断层 2：核心机制「价值印记」在代码上不可达 —— 三条路径逐一证伪

| 路径 | 为什么写不进去 |
|---|---|
| **Act 1 路径**（玩家实际走的） | `act1_state_machine.py` 从 `narrative_content.py` **只读** `imprint_name/axis/points` 再回传给 UI 显示（`:258-283`、`:351-353`、`:385-393`）。**全文没有一次调用 `add_imprint()` / `save_value_imprints()`** —— 印记只是一行要显示的字 |
| **/v1/ask 聊天路径** | `central_brain.py:584-591` 要求 `current_stage=="choice_made"` **且** `active_domain` **且** `last_choice`；而 `ask_routes.py:211-219` 构造的 context 里**根本没有** `last_choice` / `choice_importance` / `session_num` / `interaction_count`。**全 `src/` 下 grep 无任何一处给这四个键赋值** —— 它们是只被读、从不被写的幽灵字段 |
| **/engine/choice 路径**（逻辑正确） | 存在且正确（`narrative_routes.py:272-273`），但**零调用方**；且它是 `@optional_auth`，游客 `user_id=None`，被 `domain_engine.py:388 if user_id:` 直接挡掉 |

**数据印证（SQLite 实读，`data/looma.db`）：**

```
narrative_sessions      11        domain_visits            2
act1_sessions           11        narrative_events        15
─────────────────────────────────────────────────────────
value_imprints           0   ← 价值印记：0 行
navigator_memories       0   ← Navigator 记忆：0 行
emergent_strategy_log    0   ← 涌现策略：0 行
narrative_feedback       0   ← Phase 0 反馈：0 行
```

**"先打印记，才有回声" —— 印记恒空，下面这些全部连带失效：**

| 机制 | 为什么必然失效 |
|---|---|
| **跨域回声** | `_check_echo` 第一句 `if user_id not in self._imprints: return None`（`:395`），且要求单轴 ≥8 ⇒ 永不触发。矩阵 30 格写全了，**内容只写了 1 对**（`act1_state_machine.py:187 has_cross_domain = (domain == "职业域")`）⇒ **1/30** |
| **涌现策略** | `detect_strategies:498` 读 **`self.get_history("latest")`** —— 幻影 session key，全文件只有此处使用 `"latest"`，其余都是真实 `session_id` ⇒ 永远读到空历史 ⇒ 5 条涌现策略恒为 `[]` |
| **收敛点触发** | `should_trigger_convergence(..., interaction_count)` 要求 Act1 时 ≥5，而 `interaction_count` 恒为 0 ⇒ 收敛永远靠前端按 step 硬走 |
| **Navigator 深层记忆** | 挂在同一个 `last_choice` 上 ⇒ 恒空 |
| **Act 5 终极清算** | 解锁条件「总印记 ≥30」⇒ 数学上不可达。**不是没做，是永远进不去** |

### 断层 3：数据库证明这套东西从未被真正跑通过

`act1_sessions` 11 条全量展开：

| 指标 | 值 |
|---|---|
| 最深推进 | **step = 2**（单域共 0–6 步，跨域 0–10 步） |
| 做出过选择 | **0 条**（`chosen_option` 全 None，选择在第 3 步） |
| 完成 | **0 条** |
| `narrative_sessions.status` | 11/11 全部 `active`，`duration_seconds` 全部 0.0（**从未调用 `/v1/narrative/end`**） |
| 带真实身份 | 仅 **2/11**，其余 9 条 `user_id = NULL` |
| 时间窗 | **2026-08-05 ~ 2026-08-07**（两天），此后到今天 (10-25) **零活动** |
| 代码最后改动 | 2026-07-19 `e37baf4` fix(navigator) |

> **没有一次 Act 1 走到过"做出选择"这一步。**
> 也就是说：P1「选择有重量」这条支柱，在产品里**从未被哪怕一次真实执行检验过**。

### 断层 4：外部用户看到的那份，是浏览器本地演算

用户在 `PlanetX/index.html:648` 点「🪐 进入 T 空间 · Navigator 叙事体验」进的是 `narrative.html`。它：

- 自己维护 `S.imprints: {survival:0, freedom:0, belonging:0}`（`narrative.html:438`）
- **全文 `imprints` 只出现这一次** —— 既没有被累加，也没有被读取，更没有发给服务器
- 发给后端的 `current_stage` 只有三个取值：`greeting` / `open_question` / `end`（`:434, 694, 761, 786`）⇒ **永远不等于引擎要的 `domain_enter` / `choice_made`**

⇒ 即便以后把后端修好了，这条对外入口**也仍然接不上**。

### 断层 5：UI 直接写着"验证通过"，但那是纸面结论

`TspaceNavigatorScreen.tsx:658` 硬编码：
```
✅ 验证通过 — P5支柱「六域一问」成立
• 六种解读各不相同，无重复感受 ✓
• 收敛点在物理上是同一节点，在感知上是六个节点 ✓
```
好在这段代码自己留了诚实的一句（`:687`）：
> ⚠️ 注意：**纸面原型验证通过 ≠ 实际运行时成立**。实际引擎中的措辞密度、情感铺垫强度会影响质感差异的幅度。

结合断层 3 的数据：**这不是运行时验证结论，是设计时写在 JSX 里的断言。**

### 断层 6：设计文档被删 + 零测试 ⇒ 漂移无人能发现

- **零测试**：`backend/tests/` 下有 game / billing_region / intent_rules / checklist_money 等二十多个测试文件，**没有任何一个覆盖 `narrative` / `domain_engine` / `act1` / `value_imprint`**（grep 全空）。
- **契约反而先承诺了**：`docs/CN_TO_OVERSEAS_UPGRADE_CONTRACT.md:72` 把 **`active_domain`（六域当前域）** 和 **`onboarding_stage`（PlanetX 叙事进度枚举）** 列为跨区迁移时"默认带走"的产品连续性字段。
  ⇒ **契约承诺搬运一个实际不存在的状态。**

逻辑闭环是这样的：
> 7 月 1 日同天写完 GDD 和全部引擎 → 7 月 2 日 GDD 被 `chore` 清理删掉 → 之后无人能对着文档验收 → 8 月跑了两天 dev → 漂移至今无人发现。

**这跟你在主线里已经抓到的「tier 双真源」「星球等级双公式」是同一个病：
不是某一处写错了，而是缺少一个"能让人发现不一致"的机制（文档 / 契约 / CI 三者为零）。**

---

## 四、怎么才算真正落地（按优先级）

| 优先级 | 动作 | 为什么必须先做这个 |
|---|---|---|
| **P0** | **把 GDD 拽回工作区**（`git show 14e6287^:reports/…/GDD.md`），并声明它是六域的真源 | 现在是"实现存在、意图失传"，修哪个 bug 都没有判据 |
| **P0** | **统一六域名义**：二选一定真源。建议保留 GDD 版（职业/身份/诗/信任/自我/迷雾），把 `central_brain.py:40`、`seed_knowledge.py` 的功能版改名（如"六大能力模块"） | 两套同名概念是入口被抢走的根因 |
| **P0** | **接通印记链路**：让 `act1_state_machine` 在做选择时调用 `engine.add_imprint()`，或让 `/engine/act1/choice` 转发到 `DomainEngine.record_choice()` | 一行式的改动，但它是整个 GDD 的承重墙 —— 印记不通，回声/涌现/清算全是死的 |
| **P0** | 前端登录态：`/v1/narrative/start` 目前 9/11 是 guest ⇒ `add_imprint` 被 `if user_id:` 挡掉。**未登录要能玩，但必须拿到一个稳定 user_id** | 否则修好了链路还是 0 行 |
| P1 | 修 `detect_strategies` 的 `get_history("latest")` —— 改成按真实 `session_id` / `user_id` 聚合 | 幽灵 key 是明确 bug，五条涌现策略永不触发 |
| P1 | 补 external 入口：`narrative.html` 要么下掉对外链接，要么补发 `active_domain` / `last_choice` / `current_stage` 三件套 | 现在对外用户走的是一个**根本不可能产生印记**的客户端 |
| P1 | 给 Act1 补 `IMPRINT` 断言测试：跑通一次 ⇒ `value_imprints` 必须出现 1 行。**用 DB 行数做验收，不用"页面显示了印记名"** | 「显示」和「记录」的区别，就是"停留在页面上"的定义 |
| P2 | 矩阵内容补全：现在是 1/30（只有 职业域→诗域）。按 GDD §7.2 优先级补 —— 建议先做 `信任域↔迷雾域` 这对 🚫（最有戏剧性） | 矩阵写得再全，没有内容等于一张空表 |
| P2 | 决定是否继续 Act2–5。**若不做，就公开承认"我们只做了 Act 1"，并撤掉契约里的 `onboarding_stage` 承诺** | 契约承诺了就得兑现，兑现不了就撤承诺，别悬着 |

---

## 五、核查方法与边界

**实测项**：git 考古（恢复被删 GDD，定位删除提交 `14e6287` 与最后触及版本 `3361011`）→ 通读 GDD 全文 872 行 → 逐行读 `domain_engine.py` / `act1_state_machine.py` / `narrative_routes.py` / `central_brain.py:557-680` / `ask_routes.py:130-225` / `TspaceNavigatorScreen.tsx` → `ast.literal_eval` 抽出 `narrative_content.py` 的全部内容做结构化清点 → SQLite 只读打开 `data/looma.db` 实际 `COUNT(*)` 并展开 `act1_sessions.state_json`。

**边界（重要）**：
1. 没有起服务、没有发 HTTP 请求。所有"不可达"结论是**静态可达性分析 + 数据印证**，不是抓包观测。
2. `data/looma.db` 是**本机开发库**。生产环境（腾讯云 / Vultr）的行数我读不到 —— 若线上另有数据，"从未跑通"要降级为"本机从未跑通"。**这一点需要你确认生产库是否启用了 `/v1/narrative`。**
3. 过程中踩了一次自己的坑：Bash `grep` 在含中文的大文件上返回空（假阴性），差点写成"前端零网络请求"的错误结论；用 Grep 工具复核后发现 `TspaceNavigatorScreen.tsx:121` 确有 `fetch`。已按纪律：**空结果必须换工具复核后才能说"不存在"。**

---

## 附录 A｜归档位置与独立复现方式（评审者请从这一节入手）

**本文档已入仓**，欢迎复核，不必相信上面的任何一句转述：

| 项 | 值 |
|---|---|
| 仓库 | `GenzLTD/looma-zervi` |
| 分支 | `audit/planetx-six-domains-20261025` |
| 本文路径 | `docs/PLANETX_SIX_DOMAINS_DEEP_AUDIT_20261025.md` |
| 同行快照 | `docs/PLANETX_STELLAR_LEVEL_AUDIT_20261025.md`（星际等级另一份） |
| 恢复的 GDD | `reports/游戏化内测设计方案/PlanetX-T空间_游戏化预演设计_GDD.md` |

### A.1 验证恢复的 GDD 与 git 历史字节一致

被删于 `14e6287`（2026-07-02「chore: 清理旧文档和报告」），最后版本触碰于 `3361011`（2026-07-01）。
恢复后文件应与 blob `2be118272736422d6966247e34361a1045178d0f` 完全一致：

```bash
git show 14e6287^:reports/游戏化内测设计方案/PlanetX-T空间_游戏化预演设计_GDD.md \
  | git hash-object --stdin
# 期望输出：2be118272736422d6966247e34361a1045178d0f

git hash-object reports/游戏化内测设计方案/PlanetX-T空间_游戏化预演设计_GDD.md
# 期望输出同一个 hash —— 相等即证明没有任何改动被夹带进来
```

### A.2 复跑"六域从未跑通"的行数证据

```bash
cd backend
python3 -c "
import sqlite3
c = sqlite3.connect('file:data/looma.db?mode=ro', uri=True)
for t in ['narrative_sessions','narrative_events','domain_visits',
          'act1_sessions','value_imprints','navigator_memories',
          'emergent_strategy_log','narrative_feedback']:
    try:
        print(f'{t:24s}', c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0])
    except Exception as e:
        print(t, 'ERR', e)
"
```

判定标准：**后四张表只要仍为 0，本报告第三节的所有连带失效结论就依然成立**；
一旦不为 0，请回到 §3 重新核对印记写入路径（说明链路已被修好，本报告即告作废）。

### A.3 复跑 Act 1 完成度（最深 step）

```bash
cd backend
python3 -c "
import sqlite3, json
c = sqlite3.connect('file:data/looma.db?mode=ro', uri=True); c.row_factory = sqlite3.Row
for r in c.execute('SELECT session_id, state_json, updated_at FROM act1_sessions'):
    d = json.loads(r['state_json'])
    print(r['updated_at'], r['session_id'][:8], 'step=', d.get('step'),
          'completed=', d.get('completed'), 'chosen=', d.get('chosen_option'))
"
```

选择发生在第 3 步。**只要最大 `step` < 3，就意味着没有任何一次会话走到过"做出选择"。**

### A.4 复跑静态可达性（四条幽灵字段）

```bash
cd backend
grep -rn "last_choice\|choice_importance\|session_num\|interaction_count" src/ --include="*.py"
```

期望形态：只在 **读取侧**（`ask_routes.py` / `central_brain.py`）出现，
**赋值侧零命中**。若出现任何赋值语句，说明 §3.2 的结论已被修复。

### A.5 本分支未做的事（避免误读覆盖面）

本次 **没有** 改动任何一行源码 —— 纯文档入仓 + GDD 物归原主。
§4 表格里的 P0 修复动作（接通 `add_imprint`、统一六域名义、guest user_id）**均待评审后另行开工**，
请勿把本 PR 当作修复 PR 审阅。
