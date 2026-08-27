# Timeline 事件模型 · 职业时间序列真源

> **版本：** 0.1 · **日期：** 2026-07-29  
> **状态：** 产品研发契约草稿（非参赛材料）  
> **机器可读：** [timeline.v1.json](../backend/contracts/timeline.v1.json)  
> **方向真源：** `人才画像方法论批判与产品建议_20260729.md`  
> **战略裁定：** 参赛是噪声；本模型只服务「个人拥有的持续行为数据 + 长期陪伴」  
> **关联：** [TRUST_LAYER.md](./TRUST_LAYER.md) · [MANIFESTO.md](./MANIFESTO.md) · [TIMELINE_PHASE1_BACKLOG.md](./TIMELINE_PHASE1_BACKLOG.md)

---

## 0. 一句话

**Timeline 是用户拥有的、append-mostly 的职业时间线。**  
画像不是测出来的报告，而是从这条线上**浮现**的派生视图。

---

## 1. 与现有三层事件的边界（禁止混用）

| 表 / 流 | 职责 | 是否 Timeline |
|---------|------|---------------|
| `product_events` | 漏斗埋点（运营分析） | ❌ 永不当画像证据 |
| `narrative_events` | 叙事游戏会话内事件 | ❌ 可投影，非本体 |
| `trust_memories` | 信任证据原料（append-only） | ⚠️ **输入源**，可桥接到 Timeline |
| **`timeline_events`** | **用户可见的职业时间序列** | ✅ 本体 |
| `trust_attestations` | 可验证声明卡 | 下游消费 Timeline / memories |
| `game_profiles.personality_*` | 人格快照 | 仅作 **initial_hypothesis** 投影 |

```text
现有行为发生（quiz / fleet / match / ask / share / resume / …）
        │
        ├─→ product_events          （漏斗，旁路）
        ├─→ trust_memories          （信任证据原料）
        └─→ timeline_events         （职业时间线本体）← 一期新建
                    │
                    ├─→ derived_profiles / growth_curve   （派生，一期后半）
                    └─→ trust_attestations（可引用 timeline + memories）
```

**原则：** 漏斗事件 ≠ 行为证据 ≠ 职业时间线。三者可以同源触发，但表与语义必须分开。

---

## 2. 数据模型（对齐 `DatabaseManager` / SQLite 风格）

### 2.1 `timeline_events`（新建）

与现有表一致：`TEXT` UUID 主键、时间 `TEXT` ISO/`datetime('now')`、JSON 存 `*_json` 列、枚举为小写字符串。

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | TEXT PK | `tle_{uuid_short}` |
| `user_id` | TEXT NOT NULL | FK → `users.id` |
| `event_kind` | TEXT NOT NULL | 见 §3 |
| `occurred_at` | TEXT NOT NULL | 事件发生时间（可早于写入） |
| `recorded_at` | TEXT NOT NULL | 写入时间，默认 now |
| `source_system` | TEXT NOT NULL | 见 §4 |
| `source_ref` | TEXT DEFAULT '' | 源表主键或业务 id（如 `quiz_sessions.id`） |
| `title` | TEXT DEFAULT '' | 用户可读短标题 |
| `summary` | TEXT DEFAULT '' | 一句话摘要（可空） |
| `payload_json` | TEXT DEFAULT '{}' | 结构化载荷（按 kind 校验） |
| `signal_quality` | TEXT NOT NULL DEFAULT 'observed' | `self_report` \| `observed` \| `external` \| `hypothesis` |
| `confidence` | REAL DEFAULT 0.5 | 0–1，**内部用**；稀疏/自评自动压低 |
| `weight_role` | TEXT NOT NULL DEFAULT 'evidence' | `hypothesis` \| `evidence` \| `calibration` |
| `visibility` | TEXT NOT NULL DEFAULT 'private' | `private` \| `l1` \| `l2` \| `l3` |
| `consent_scope` | TEXT DEFAULT '[]' | JSON：可授权给谁/何种场景 |
| `status` | TEXT NOT NULL DEFAULT 'active' | `active` \| `superseded` \| `deleted` |
| `superseded_by` | TEXT DEFAULT NULL | 修正链 |
| `created_at` | TEXT | |
| `updated_at` | TEXT | |

**索引建议：**

- `(user_id, occurred_at DESC)` — 时间线拉取
- `(user_id, event_kind, occurred_at)` — 按类过滤
- `(source_system, source_ref)` — 幂等桥接 / 去重

**写入约定（对齐现有 `insert_trust_memory` 风格）：**

- 业务路径调用 `DatabaseManager.insert_timeline_event(...)`
- 同一 `(user_id, source_system, source_ref, event_kind)` **幂等**（`check_in` 等允许多次的 kind 除外）：重复写入更新 `payload_json` / `updated_at`
- 用户删除 → `status='deleted'`（被遗忘权）

### 2.2 `derived_profiles`（一期后半，可延后建表）

| 列 | 说明 |
|----|------|
| `user_id` | PK / UNIQUE |
| `skill_vector_json` | 能力维度向量 |
| `growth_curve_json` | 时间桶 × 维度 |
| `motivation_pattern_json` | 动机模式 |
| `data_density` | 事件数 / 活跃周数等 |
| `confidence_overall` | 总置信度；稀疏时强制降低 |
| `hypothesis_weight` | 人格等初始假设当前权重（0–1，随时间衰减） |
| `computed_at` | 上次重算时间 |
| `version` | 算法版本字符串 |

一期可先 **API 实时聚合**，表可第二迭代再落库。

### 2.3 人格结果的定位（冲突消解）

| 现状 | 一期裁定 |
|------|----------|
| `game_profiles.personality_type` 当核心卖点 | **保留字段**，产品语义改为 **初始假设** |
| quiz 完成写 trust_memory + `quiz_complete` | 额外写一条 `timeline_events`：`event_kind=initial_hypothesis`，`weight_role=hypothesis` |

衰减策略（产品层）：

| 用户活跃月数 | 建议 hypothesis 权重上限 |
|--------------|---------------------------|
| 0–1 | 1.0 |
| 1–3 | 0.7 |
| 3–6 | 0.3 |
| 6+ | 0.1 |

---

## 3. `event_kind` 枚举（一期只开子集）

### 3.1 一期必开（P0）

| kind | 含义 | signal_quality 默认 | 主要 source |
|------|------|---------------------|-------------|
| `initial_hypothesis` | 人格/冷启动假设 | `hypothesis` | `quiz` |
| `quiz_completed` | 完成测评（事实节点） | `observed` | `quiz` |
| `project_record` | 项目经历结构化记录 | `self_report` | `manual` |
| `check_in` | 每周轻量签到 | `self_report` | `manual` |
| `interaction_log` | 与 AI/教练对话摘要节点 | `observed` | `ask` |
| `share_authorized` | 用户授权分享画像 | `observed` | `share` |
| `match_scan` | 完成一次职位匹配扫描 | `observed` | `match` |
| `resume_ingest` | 简历解析后的摘要节点 | `observed` | `resume` |

### 3.2 一期 stub、二期实装（P1）

| kind | 说明 |
|------|------|
| `learning_activity` | 站内学习轨迹 |
| `career_decision` | 跳槽/拒 offer 等决策记录 |
| `interview_session` | AI 模拟面试行为（高价值行为源） |
| `fleet_co_presence` | 舰队共在 |
| `external_signal` | GitHub 等授权外部信号 |
| `emotion_signal` | 诗词/白噪音等情绪触点（不阻塞主线） |

**明确不进 Timeline：** 参赛话术、设计外包交付物、竞赛创新点清单本身。

---

## 4. `source_system` 枚举

| 值 | 对应现有系统 |
|----|----------------|
| `quiz` | `quiz_sessions` / `game_routes` |
| `trust_memory` | `trust_memories` 桥接 |
| `match` | `match_reports` |
| `share` | `share_codes` / referral 分享 |
| `resume` | resume 上传路径 |
| `ask` | Ask / 对话 |
| `fleet` | fleets / missions |
| `manual` | 用户主动记录 / check-in |
| `interview` | 未来模拟面试 |
| `external` | 外部授权源 |
| `system` | 衰减重算、校准写入 |

---

## 5. 载荷约定（`payload_json` 最小字段）

```json
// initial_hypothesis
{
  "personality_type": "超新星领航员",
  "personality_detail_ref": "game_profiles",
  "label": "initial_hypothesis",
  "decay_class": "bei_like"
}

// project_record
{
  "role": "后端",
  "outcome": "上线匹配报告 API",
  "skills_guess": ["python", "api"],
  "raw_text_chars": 420
}

// check_in
{
  "mood": "focused",
  "focus": "找工作",
  "blocker": null
}

// share_authorized
{
  "share_code_prefix": "sc_",
  "scope": ["identity"],
  "channel": "hr_link"
}
```

禁止写入：邮箱、手机、身份证、明文简历全文、密码、token（对齐 `analytics/events.py` 的 PII 剥离精神）。

---

## 6. API 草图（`/v1/timeline/*`）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/v1/timeline` | 当前用户时间线；`cursor` / `limit` / `kind` / `since` |
| `POST` | `/v1/timeline/events` | 手动写入（`project_record` / `check_in`） |
| `PATCH` | `/v1/timeline/events/:id` | 修正；可 `supersede` |
| `DELETE` | `/v1/timeline/events/:id` | 软删 |
| `GET` | `/v1/timeline/growth` | 派生成长曲线；不足时 `confidence=low` |
| `POST` | `/v1/timeline/bridge/backfill` | 历史 quiz/match/share 幂等灌入 |

T空间授权：沿用 `share_codes.scope`；Timeline 只做 **按 L1/L2/L3 过滤事件**，不另造分享码。

平台头：`X-Platform`: `planetx_web` | `planetx_mp` | `tspace_web`。

---

## 7. 隐私与数据主权（一期写进实现）

1. 默认 `visibility=private`  
2. 分享只暴露授权等级对应子集  
3. 删除：软删 + 派生剔除  
4. 置信度与「数据不足」必须对用户可见，禁止伪精确

---

## 8. 与 Trust 层的协作

| Trust | Timeline |
|-------|----------|
| 回答「某次交集能否支撑声明」 | 回答「职业轨迹随时间如何长」 |
| `evidence_refs` → `trust_memories.id` | 一期并行；二期可增 `timeline_refs` |

**不要**用 Timeline 替换 Trust；**不要**用 Trust 冒充时间厚度。

---

## 9. 非目标（防噪声回潮）

- ❌ 参赛「五大创新点」驱动表结构  
- ❌ 鸿蒙元服务 / 设计稿张数当作 Timeline 依赖  
- ❌ XP/舰队等级当作能力真值（最多前端皮肤）  
- ❌ 一期做完整技能图谱 / 轨迹预测

---

## 10. Schema SQL 草案（供 `manager.py` 落地）

```sql
CREATE TABLE IF NOT EXISTS timeline_events (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL,
    event_kind        TEXT NOT NULL,
    occurred_at       TEXT NOT NULL,
    recorded_at       TEXT NOT NULL DEFAULT (datetime('now')),
    source_system     TEXT NOT NULL,
    source_ref        TEXT DEFAULT '',
    title             TEXT DEFAULT '',
    summary           TEXT DEFAULT '',
    payload_json      TEXT DEFAULT '{}',
    signal_quality    TEXT NOT NULL DEFAULT 'observed',
    confidence        REAL DEFAULT 0.5,
    weight_role       TEXT NOT NULL DEFAULT 'evidence',
    visibility        TEXT NOT NULL DEFAULT 'private',
    consent_scope     TEXT DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'active',
    superseded_by     TEXT DEFAULT NULL,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_timeline_user_time
    ON timeline_events(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_user_kind
    ON timeline_events(user_id, event_kind, occurred_at);
CREATE INDEX IF NOT EXISTS idx_timeline_source
    ON timeline_events(source_system, source_ref);
```

实现位置：`backend/src/db/manager.py` · `backend/src/api/routes/timeline_routes.py` · `backend/src/app.py` · `backend/contracts/timeline.v1.json`。
