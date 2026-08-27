# Timeline 一期 Backlog · 6–8 周

> **日期：** 2026-07-29  
> **依据：** [TIMELINE_EVENT_MODEL.md](./TIMELINE_EVENT_MODEL.md) · 战略裁定「参赛噪声 / 产品主线」  
> **目标：** 用户能看见「时间在长」；人格降级为初始假设；现有闭环继续可用  
> **工程约束：** 对齐现有 backend（`DatabaseManager` + `*_routes.py` + SQLite，无 Alembic）

---

## 0. 一期成功标准（DoD）

1. 新用户完成 quiz 后，Timeline 出现 `quiz_completed` + `initial_hypothesis`，文案标明「初始假设」。  
2. 历史用户登录可 backfill：quiz / share / match / resume 幂等灌入。  
3. 用户可每周 `check_in`、可添加 `project_record`。  
4. `GET /v1/timeline/growth` 在事件 < 阈值时返回 **低置信度 + 诚实空态**，不伪精确。  
5. 现有 PlanetX→T空间分享导入闭环 **不被破坏**（回归 `test_closed_loop` / 演示稿路径）。  
6. **不做：** 鸿蒙上架、设计外包二期、完整模拟面试产品化、技能图谱预测。

---

## 1. Epic 总览

| Epic | 主题 | 周次（建议） | 优先级 |
|------|------|--------------|--------|
| E0 | 契约与表结构落地 | W1 | P0 |
| E1 | 写入桥接（把现有行为灌进 Timeline） | W1–W2 | P0 |
| E2 | Timeline API + 测试 | W2–W3 | P0 |
| E3 | PlanetX：时间线 + check-in + 项目记录 | W3–W5 | P0 |
| E4 | 成长曲线（最小派生）+ 假设衰减 | W5–W6 | P0 |
| E5 | T空间：授权可见厚度（L1/L2） | W6–W7 | P1 |
| E6 | 留存钩子验证与数据密度仪表 | W7–W8 | P1 |

---

## 2. 拆解任务（按现有文件）

### E0 — 契约与表结构（W1）

| ID | 任务 | 落点 | 验收 |
|----|------|------|------|
| E0.1 | 合并 `timeline.v1.json` 契约 | `backend/contracts/timeline.v1.json` | 枚举与模型文档一致 |
| E0.2 | `SCHEMA_SQL` 增加 `timeline_events` + 索引 | `backend/src/db/manager.py` | 冷启动 `init_schema` 建表成功 |
| E0.3 | CRUD：`insert_timeline_event`（幂等）、`list_timeline_events`、`soft_delete_timeline_event`、`supersede_timeline_event` | `manager.py` | 单测覆盖幂等与软删 |
| E0.4 | 常量模块：`event_kind` / `source_system` / PII 过滤 | 新建 `backend/src/timeline/constants.py`（或 `events.py`） | 与 analytics 风格一致，禁止 PII 键 |

### E1 — 写入桥接（W1–W2）

| ID | 任务 | 落点 | 验收 |
|----|------|------|------|
| E1.1 | quiz 完成 → `quiz_completed` + `initial_hypothesis` | `game_routes.py`（profile-sync / quiz complete 路径） | 不替代现有 trust_memory / `quiz_complete` 埋点 |
| E1.2 | 分享码创建 → `share_authorized` | trust / referral 发码路径 | `source_ref` 可追溯 |
| E1.3 | match 报告保存 → `match_scan` | `match_report_routes` / `match_report_manager` | 仅在「已保存」时写，避免空报告噪声 |
| E1.4 | resume 解析完成 → `resume_ingest`（摘要节点，无全文） | `resume_routes.py` | payload 无简历正文 |
| E1.5 | Ask 会话结束摘要 → `interaction_log`（可先 stub 标题） | ask 相关 routes | 失败不影响主对话 |
| E1.6 | `POST /v1/timeline/bridge/backfill` | `timeline_routes.py` | 对当前用户幂等；可重复调用 |

### E2 — Timeline API（W2–W3）

| ID | 任务 | 落点 | 验收 |
|----|------|------|------|
| E2.1 | Blueprint `timeline_bp` + 注册 | `timeline_routes.py` · `app.py` | `/v1/timeline` 需登录 |
| E2.2 | `GET /v1/timeline` 游标分页 | 同上 | 默认排除 `deleted` |
| E2.3 | `POST /v1/timeline/events` 仅允许 manual kinds | 同上 | 拒写 `initial_hypothesis` 等系统 kind |
| E2.4 | `PATCH` / `DELETE` | 同上 | 只能改自己的事件 |
| E2.5 | 测试 | `backend/tests/test_timeline.py` | 列表 / 写入 / 幂等 backfill / 软删 |

### E3 — PlanetX 前端（W3–W5）

| ID | 任务 | 落点 | 验收 |
|----|------|------|------|
| E3.1 | shared-core：Timeline 类型与 API client | `frontend/packages/shared-core` | 与契约字段对齐 |
| E3.2 | 「我的时间线」页（列表 + 空态） | `frontend/packages/planetx` | 有事件可见；无事件引导 check-in / 记项目 |
| E3.3 | 人格结果页文案：标注「初始假设，将随行为更新」 | 结果页 / Hub | 不删测评，只改定位 |
| E3.4 | 每周 check-in 轻量表单（mood / focus / blocker） | planetx | 写入 `check_in` |
| E3.5 | 添加项目记录表单 | planetx | 写入 `project_record` |
| E3.6 | Hub 入口：时间线与测评并列，测评不再独占「核心」文案 | `HubScreen.tsx` 等 | 去噪声叙事 |

### E4 — 成长曲线最小派生（W5–W6）

| ID | 任务 | 落点 | 验收 |
|----|------|------|------|
| E4.1 | `GET /v1/timeline/growth` 实时聚合 3 个维度（先规则，后 LLM） | `timeline/` 或 `agents/` 小模块 | 维度建议：表达沉淀 / 行动密度 / 探索广度（可改名，但要固定） |
| E4.2 | `hypothesis_weight` 按活跃月数衰减 | growth 响应字段 | 与模型文档表一致 |
| E4.3 | 数据不足：`confidence=low` + `message` | API + UI | 禁止假满分雷达 |
| E4.4 | （可选）`derived_profiles` 落表缓存 | `manager.py` | 非阻塞；可 W8 再做 |

### E5 — T空间厚度消费（W6–W7，P1）

| ID | 任务 | 落点 | 验收 |
|----|------|------|------|
| E5.1 | 分享公开页：L1 显示项目摘要节点数 / 最近活跃 | `saas` 候选人分享视图 | 无授权不露 L2 |
| E5.2 | L2：成长曲线（用户二次授权 scope） | share scope 扩展或映射 | 与现有 `share_codes` 兼容 |
| E5.3 | 空厚度诚实展示 | UI | 「尚无足够行为沉淀」 |

### E6 — 留存与密度（W7–W8，P1）

| ID | 任务 | 落点 | 验收 |
|----|------|------|------|
| E6.1 | 定义「活跃周」：≥1 次 check_in 或 project_record 或 quiz/match | 文档 + 简单 SQL/metric | 能回答嘟嘟「采什么」 |
| E6.2 | 内部仪表：人均事件数、第 2/4 周留存（可用 `product_events` 旁路） | 脚本或简单 admin | 不做成参赛大屏 |
| E6.3 | 决策备忘：模拟面试是否升 P0（二期） | 短文档 1 页 | 用一期数据密度说话 |

---

## 3. 明确 Out of Scope（一期砍掉 / 缓做）

| 项 | 处置 | 原因 |
|----|------|------|
| 鸿蒙元服务真机 | 缓 | 生态支线，非时间序列本体 |
| 设计外包二阶段大单 | 缓 | 先验证行为层再买视觉 |
| AI 模拟面试完整产品 | 二期候选 | 高价值，但一期先打通写入与可见 |
| 诗词/情绪陪伴进主路径 | 缓 | 差异化，不阻塞 |
| 游戏化 XP=能力 | 不做 | 最多皮肤，不当真值 |
| 重写参赛 BP / 报名表 | 不做 | 噪声 |

---

## 4. 依赖与风险

| 风险 | 缓解 |
|------|------|
| 与 `trust_memories` 双写增加复杂度 | 桥接失败只打日志，不阻断主路径（对齐 `log_product_event` best-effort） |
| 前端时间线做成「又一个仪表盘」 | 只做时间流 + 一个成长视图；禁止堆统计卡片 |
| 人员被合规/鸿蒙支线拉走 | 支线并行，**不占用 E0–E4 负责人主时间** |
| 数据稀疏导致「陪伴」空洞 | check_in 必须在 E3 交付；growth 必须诚实空态 |

---

## 5. 建议工时切分（小团队）

| 角色 | 主责 |
|------|------|
| Backend | E0–E2、E4.1–E4.3、E1 全桥接 |
| PlanetX | E3、E4 UI |
| T空间 | E5（可错后一周） |
| 产品 | E3 文案「初始假设」、E6.3 决策、拒绝噪声需求 |

---

## 6. 下一行动（本周即可开工）

1. Review 通过本文 + `TIMELINE_EVENT_MODEL.md` + `timeline.v1.json`  
2. 开分支实现 **E0.2 + E0.3 + E2.1 空壳路由**（先通再美）  
3. 在 `game_routes` quiz 完成路径挂 **E1.1**（最小双写）  
4. 同步更新 `docs/MANIFESTO.md` 或架构文档一句交叉引用（可选，避免大改）

---

## 7. 一句话给团队

> 一期只做一件事：让行为有地方长、让用户看得见长、让人格退居假设。其余都是噪声。
