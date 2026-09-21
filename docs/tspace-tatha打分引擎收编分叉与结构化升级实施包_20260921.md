# tspace-tatha 打分引擎收编分叉与结构化升级实施包（2026-09-21）

> 版本：v1.2（BE-3 增补 3.8/3.9：VACUUM 页级擦除 + 备份快照对齐 + LLM 出境脱敏；承诺口径定为「分层可验证删除」，不承诺阅后即焚式绝对保证）  
> 日期：2026-09-21  
> 用途：团队 owner 评审与拍板  
> 口径：方案级（待评审），未实施；owner 通过后走 ADR 通道落 PR

## 一、背景与结论摘要

**已验证事实**（2026-09-21 tspace × tatha 实地调研）：

| 调研点 | 结论 |
|---|---|
| tspace.genz.ltd 打分后端 | 即 looma `/v1/jobs/match` → `src/pipeline/job_match_pipeline.py`；文件头自述 *"Migrated from Tatha's scoring engine"* |
| 同一引擎两套实现 | tatha（gfcc 生态）= pydantic_ai 结构化输出；looma（tspace 宿主）= 手写 prompt + `json.loads` + `_default_score` 静默兜底 |
| 模型能力三模型对比 | 3b 幻觉致命、7b 忠实可用、deepseek-chat 全维度最优（含「未提及薪资按中性处理」类元判断） |
| looma 现有兜底机制 | `LLM_PROVIDER_ORDER=deepseek,ollama` 已在 `src/config.py:84` 内置——offline fallback 已存在，无须新建设 |
| T 空间前端 UI 字段消费 | `scores.overall` / `fit_bullets` / `gap_analysis` / `missing_skills` / `improvement_plan` 共 5 大块、11 维 score——**改造纯后端，前端不动** |

**核心结论**：tspace 已经是 tatha 引擎的商业化宿主。问题不是「要不要接 tatha」，而是**分叉的两套实现各自演化，存在三类静默风险**：

| 风险 | 位置 | 表现 |
|---|---|---|
| **静默降级返回伪分** | `job_match_pipeline.py:113-118` → `_default_score()` line 236 | LLM 解析失败时返回 50/15/15/5 全维默认 + summary「AI 评分暂不可用」——前端 `scores.overall` 正常显示「50 分」，用户误以为真分 |
| **模型护栏缺失** | `central_brain.py:139 _call_llm` + `config.py:84 LLM_PROVIDER_ORDER` | 仅环境变量白名单，无 schema/常量校验白名单；误配 3b 模型可上生产（求职者会收到编造的技能匹配） |
| **评测无回归集** | 全仓无黄金集 | 任何 prompt/模型/schema 变更无回归依据；9-21 三模型对比是一次性手跑 |
| **撤回同意不删数据** | `consent.py ConsentManager.revoke` 只改 `consents.status` | PIPL 第 15 条「撤回同意应当主动删除」不满足：用户撤了 `jobseeker_core`，已生成的 match 报告与已提取简历数据仍留存库中——「隐私自主可控」承诺只兑现「授权可控」一半 |
| **删简历无级联** | `resume_routes.delete_resume`（line 614）只 `DELETE FROM documents` | `match_report.resume_id` 关联报告、LLM analysis 不清；用户以为删净，报告仍可被分享 |

## 二、目标与原则

### 业务目标
1. **消除静默降级**：所有非全维成功的打分必须带 `degraded:true` 标记，前端可选择显示「降级中」徽标
2. **白名单护栏**：模型/config 选择能上线 LLM_ALLOWED_MODELS 校验，防止 3b 误配进生产
3. **黄金评测集**：常驻的 resume × jd × 期望分集合，任何变更跑回归
4. **隐私承诺闭环**：撤回同意即触发覆盖数据清理；删简历级联清关联报告；提供聚合删除入口——「个人隐私权限由用户自主可控」从「授权可控」补全到「撤回即删」

### 架构原则
- **tatha = 引擎实验场**：新模型 / 新 schema / 新 prompt 先在 tatha 隔离实例验证
- **looma = 商业化宿主**：验证过的东西迁回 looma；不再出现「两边各自演化」的分叉
- **schema 以 looma 11 维为准**：UI 已消费，向下不兼容变更禁用
- **零新建设**：优先利用 `LLM_PROVIDER_ORDER` 现成机制，不重造 provider 路由层

### 不在本期范围
- 不重写 tatha 本尊（pydantic_ai 结构化是 tatha 自有生态，不是问题源头）
- 不改 UI（Jobs.tsx 已消费 looma 全 schema）
- 商业化四件套中配额/信任/时间线不动；**consent 例外**——BE-3 只加撤回触发的清理钩子，不改授权模型与 `require_consent` 拦截逻辑

## 三、改造范围（明确边界）

### 要动（BE-3 新增 5 个文件）
| 路径 | 函数/行号 | 变更类型 |
|---|---|---|
| `backend/src/config.py` | `LLM_PROVIDER_ORDER` line 84、`Config` 同名 line 247 | 新增 `LLM_ALLOWED_MODELS` 白名单常量与 env 绑定 |
| `backend/src/agents/central_brain.py` | `_call_llm` line 139 入口 + 新增 `LLMAllowedError` 异常 | 加白名单校验 + 显式 raise（不静默吞） |
| `backend/src/pipeline/job_match_pipeline.py` | `_score_resume_vs_job` line 16、`run_job_match_pipeline` line 272 | 返回结构增加 `degraded` / `degrade_reason`；`on degraded` 不污染其他匹配项 |
| `backend/src/compliance/consent.py` | `ConsentManager.revoke`（line ~176） | revoke 成功后触发 `_purge_scope_data(uid, scope)`（宽限期模式） |
| `backend/src/api/routes/resume_routes.py` | `delete_resume` line 614 | 级联删除 `match_report.resume_id` 关联报告 + analysis；新增 `purge_all` 路由 |
| `backend/src/api/routes/compliance_routes.py`（或新 `privacy_routes.py`） | 新增 `POST /privacy/purge_all`、`GET /privacy/data_inventory` | 聚合删除入口 + 用户数据清单查询（先看后删） |
| `tests/test_consent_purge.py`（新） | — | 撤回→清理、级联删除、purge_all 的单测 |
| `tests/fixtures/golden_resume_match.json`（新） | — | 黄金评测集：孙静雯 + 赵元正 + 3-5 个其他简历 × mock 全部 JD |

### 不动（验证边界）
- `frontend/packages/saas/src/features/hr/Jobs.tsx`（消费现有 schema）
- `backend/src/api/routes/jobs_routes.py`（`/v1/jobs/match` 入口契约不变）
- tatha `~/Projects/gfcc/services/tatha/`（本轮不归一，验证完不迁）
- 配额/信任/时间线路由（BE-3 不触碰；consent 仅加清理钩子不改拦截逻辑）

## 四、实施步骤（Task Pack 拆解）

### 📦 Task Pack BE-1：模型白名单护栏（后端工程师，工时 1 天）

**目标**：禁止 3b 级模型上生产；model 名解析失败的任意消息升级为异常而非静默。

| 编号 | 任务 | 产出 |
|---|---|---|
| BE-1.1 | `config.py:84` 旁增 `LLM_ALLOWED_MODELS`（默认 `["deepseek/deepseek-chat", "ollama/qwen2.5:7b"]`）；env 绑定 `LLM_ALLOWED_MODELS` | 白名单常量；环境变量生效路径同 `LLM_PROVIDER_ORDER` |
| BE-1.2 | `central_brain._call_llm` 入口加白名单校验：模型名不在白名单 → raise `LLMAllowedError` | 异常类（带 `model`/`allowed_list` 属性） |
| BE-1.3 | `_call_llm` 已有 try/except + provider 循环；把解析失败的 `return None` 改为 raise `LLMCallFailedError`（带 `reason` 属性）；`_default_score` 由调用方显式 catch | 上抛而非静默 |
| BE-1.4 | 单测：白名单 reject 3b / reject 非法名 / accept deepseek+7b；现有 `tests/test_central_brain.py` 全绿 |

**验收**：
- env `LLM_PROVIDER_ORDER=ollama/qwen2.5:3b`（不在白名单）→ 进程拒绝启动或在首次 _call_llm 抛 `LLMAllowedError`
- env 非法 / 缺省 → 不接受 3b 默认兜底（必须显式开白名单才放行）

### 📦 Task Pack BE-2：消除静默降级（后端工程师，工时 1.5 天）

**目标**：LLM 失败时不返回伪分；返回结构带 `degraded:true`；其他匹配项不受单点失败污染。

| 编号 | 任务 | 产出 |
|---|---|---|
| BE-2.1 | `job_match_pipeline._score_resume_vs_job`（line 16）改造：try 块包裹 `_call_llm` + `json.loads` + `_sanitize_scores`；任何步骤抛错 → 返回 `_default_score() + {"degraded": True, "degrade_reason": <class:msg>}` | degrade 标记位 |
| BE-2.2 | `run_job_match_pipeline`（line 272）改逐职位 try：单职位失败不连坐其他职位；最终响应顶层 `has_degraded: bool` + `degraded_count: int` | 失败隔离 |
| BE-2.3 | `jobs_routes.job_match`（line 364）响应 schema 增加 `degraded` 字段（默认 `false`），OpenAPI 同步更新 | API 契约向后兼容（新增可选字段） |
| BE-2.4 | 单测：mock `_call_llm` 抛错 → match 含 degraded=true、scores 全默认；mock 全失败 → has_degraded=true、degraded_count=N |

**验收**：
- 故意让 _call_llm 失败（删 key / 关网）→ `/v1/jobs/match` 响应 200 + degraded=true + summary「AI 评分暂不可用」+ scores 全 50 默认值；前端 `scores.overall` 显示「50（降级）」
- 单职位失败不影响其他职位

### 📦 Task Pack BE-3：撤回级联清理（隐私承诺闭环，后端工程师，工时 2 天）

**背景**：2026-09-21 代码核查结论——consent 机制「授权可控」真实落地（三层授权包 + `require_consent` API 强拦截 + `ConsentSettings.tsx` 前端开关 + 全量审计），但「撤回即删」闭环缺失：`ConsentManager.revoke` 只改 `consents.status`，不触发数据清理；`delete_resume` 无级联。**公开承诺「个人隐私权限由用户自主可控」前必须补全**，否则是 PIPL 合规敞口。

**目标**：撤回同意 → 覆盖数据按宽限期清理；删简历 → 级联清关联报告；提供聚合删除入口。

| 编号 | 任务 | 产出 |
|---|---|---|
| BE-3.1 | **撤回触发的数据清理**：`consent.py ConsentManager.revoke` 成功后调用 `_purge_scope_data(uid, scope)`；默认宽限期模式（`PRIVACY_PURGE_GRACE_DAYS`，建议 30 天，PIPL 允许）——宽限期内 re-grant 可恢复；到期硬删 | 撤回→清理钩子 + 宽限期任务 |
| BE-3.2 | **scope→数据映射表**：`SCOPE_DATA_MAP` 常量，定义每个 scope 覆盖哪些表/字段（`jobseeker_core` → documents(doc_type=resume) + match_report + timeline events；`credit_query` → credit 分析结果；`report_share` → 分享链接失效即 revoke_share_code 等价） | 映射常量，随 scope 演化维护 |
| BE-3.3 | **删简历级联**：`resume_routes.delete_resume`（line 614）在删 documents 行后，级联 `DELETE FROM match_report WHERE resume_id=? AND user_id=?` + 清 LLM analysis 缓存；响应带 `cascaded: {match_reports_deleted: N}` | 级联删除 |
| BE-3.4 | **聚合删除端点**：`POST /privacy/purge_all`（密码/二次确认验证），一次性清简历+报告+时间线+分享码；`GET /privacy/data_inventory` 返回用户全部数据清单（先看后删，PIPL 知情权） | privacy 路由 |
| BE-3.5 | **前端设置页**：`ConsentSettings.tsx` 增「删除我的全部数据」入口（红色确认弹窗 + 输入「删除」二次确认）；撤回 consent 弹提示「N 天后相关数据将被删除」 | UI 闭环 |
| BE-3.6 | **单测**：`tests/test_consent_purge.py`——撤回 jobseeker_core → 30 天后简历+报告清空；宽限期内 re-grant → 数据保留；delete_resume → match_report 级联清；purge_all → 全清单空 | 测试套件 |
| BE-3.7 | **审计增强**：purge 动作写 audit_log（`privacy_purge` / `privacy_purge_all`），含删除资源计数，不可抵赖 | 审计闭环 |
| BE-3.8 | **页级擦除与备份对齐**：硬删流程末尾执行 SQLite `VACUUM`（重写数据库文件、消除删除数据在空闲页/预写日志的残留）；部署层备份快照保留期（腾讯/天翼/Vultr 卷快照）核查 ≤ 宽限期 30 天，超出则收紧；`llm_usage` 审计表已核实**不存 prompt 原文**（`manager.py:444-456`，仅 tokens/cost/latency），无额外清洗负担 | 文件级擦除 + 备份滚动对齐 |
| BE-3.9 | **LLM 出境最小化**：打分/分析 prompt 组装前对简历文本做敏感字段剥离（身份证号/手机号/住址/出生日期正则 + 姓名可选脱敏标记）；隐私政策同步声明「向 AI 服务商发送脱敏后的必要信息」——同时覆盖 PIPL「向第三方提供个人信息需单独同意」的合规点 | prompt 脱敏函数 + 政策披露 |

**验收**：
- grant jobseeker_core → 上传简历 + 生成报告 → revoke → 30 天后（或手动触发宽限期到期任务）简历与报告均不可查，revoke 后立即查 `GET /privacy/data_inventory` 显示「待删除（宽限期至 XX 日）」
- `delete_resume` 后：`match_report` 中该 resume_id 报告数为 0，分享链接失效
- `POST /privacy/purge_all` 后：data_inventory 全空；audit_log 有完整删除记录
- 宽限期内 re-grant → 数据恢复可用（软删机制）
- 硬删后 `data/looma.db` 经 `VACUUM` 重写，hex dump 检索被删简历关键内容无命中
- 打分 prompt 出境文本不含身份证号/手机号（单测正则断言）
- **承诺口径**：对外话术为「撤回后 30 天内从我们数据库与备份中彻底删除；向 AI 服务商发送的是脱敏后必要信息」——不使用「阅后即焚」式绝对保证（deepseek 服务端收到过的明文不可由我方删除，隐私政策如实披露该边界）

### 📦 Task Pack QA-1：黄金评测集（QA 工程师 + 后端共享，工时 1 天）

**目标**：常驻自动评测，回归评估用。

| 编号 | 任务 | 产出 |
|---|---|---|
| QA-1.1 | `tests/fixtures/golden_resume_match.json` 建数据集：3-5 份真实脱敏简历（孙静雯/赵元正为种子已脱敏）+ 全部 mock JD × 期望分数区间（人工标注，标注者=owner 本人/受信任审核员） | 评测集文件 |
| QA-1.2 | `tests/test_golden_match.py`：遍历评测集调 `_score_resume_vs_job`，断言 scores 在期望区间、fit_bullets 长度≥3、missing_skills 长度≥1、improvement_plan 非空 | pytest 套件 |
| QA-1.3 | CI：`tests-golden` job（GitHub Actions 新增）；变更 job_match_pipeline / central_brain / config 时必跑；带 LLM cost gate（深度求 >$0.5 跳过默认） | 回归门槛 |

**验收**：
- 跑 `pytest tests/test_golden_match.py -v` 100% 通过
- 故意把 schema 改坏（删 improvement_plan 字段）→ 测试失败
- 故意换 3b 模型（被护栏拦）→ 测试不启动或显式失败

### 📦 Task Pack FS-1：部署与可观测性（全栈/DevOps，工时 0.5 天）

**目标**：线上配置改完立即生效且可观测。

| 编号 | 任务 | 产出 |
|---|---|---|
| FS-1.1 | 三端（腾讯 / 天翼 / Vultr）`docker/.env` 增 `LLM_ALLOWED_MODELS`（保守默认同 `LLM_PROVIDER_ORDER` 现有白名单） | 部署配置 |
| FS-1.2 | `llm_usage` 审计表增 `degraded` / `model_allowed` 列（如未存在） | 可观测性 |
| FS-1.3 | deploy.yml 增 `tests-golden` job 入口（与 FS-1.3 对接） | CI 集成 |

**验收**：
- 腾讯 health 后 `llm_usage` 表新增字段有值
- deploy.yml 三端一致

## 五、验收标准（owner 拍板判据）

| 项 | 通过判据 |
|---|---|
| BE-1 白名单护栏 | `LLM_ALLOWED_MODELS` 未设 3b 时强行启动失败；已有测试覆盖 |
| BE-2 静默降级消除 | 注入 _call_llm 失败 → API 响应含 degraded=true；前端可观测 |
| BE-3 隐私承诺闭环 | 撤回 jobseeker_core → 宽限期后简历+报告清空；delete_resume 级联清 match_report；purge_all 后 data_inventory 全空且 audit 留痕 |
| QA-1 黄金集 | 5 份简历 × mock JD 100% 通过；CI 每次变更必跑 |
| FS-1 部署对齐 | main push → 三端 health ok + LLM_ALLOWED_MODELS 生效 |
| 性能基线 | deepseek-chat 单份 top_n=2 < 60s（已有 18-32s 基线，保留 2x 余量） |
| 端到端 | 完整流程：tspace.genz.ltd → jobs/match 200 + 含真实分数（非 50 默认） |

## 六、风险与备选

| 风险 | 等级 | 缓解 / 备选 |
|---|---|---|
| `_call_llm` 抛错改造可能影响现有调用方 | 中 | 改动入口处 raise，业务调用方（job_match_pipeline）显式 catch；不在一个 PR 同时改 prompt 与 raise |
| 黄金集人工标注耗时 | 中 | 种子（孙静雯/赵元正）已有 9-21 实测期望分数；其余简历 owner 提供语料 + 期望区间，不必另请标注员 |
| 11 维 schema 不能向下兼容（UI 锁定） | 低 | 改造只在「不变 schema」前提下加 degrade 标记，无 UI 影响 |
| deepseek API 偶发格式异常 → degrade 频繁 | 中 | degrade 频次纳入 SLO 看板；频繁触发自动告警 |
| 宽限期软删与硬删的实现复杂度 | 中 | 首版用 `purge_after` 时间戳 + 每日定时任务扫描；不引入新中间件 |
| 级联删除误删（match_report 按 user_id + resume_id 双条件） | 低 | 级联 SQL 双条件 + 单测覆盖；audit_log 记录删除计数可对账 |
| 「删除我的全部数据」被恶意触发（账号被盗） | 中 | 密码/二次输入确认 + 宽限期 30 天内可联系客服恢复（软删） |
| deepseek 服务端已收到明文、我方不可删 | 低（已披露） | 隐私政策如实披露出境边界 + 依赖 API 提供商数据保留政策（API 输入默认不用于训练）；BE-3.9 脱敏将出境敏感度降到最低 |

## 八、给 owner 的评审项（yes/no 决策）

1. **是否批准**走 ADR 通道进入 PR？（Y/N）
2. **是否同意** Task Pack BE-1 / BE-2 / BE-3 / QA-1 / FS-1 的工时估算？（Y/N；如 N 请提供其他口径）
3. **黄金集来源**：owner 提供脱敏语料（Y），还是仅用 9-21 的两份种子（Y）？建议前者
4. **白名单默认值**是否同意 `["deepseek/deepseek-chat", "ollama/qwen2.5:7b"]`？（Y/N；如 N 请指定默认白名单）
5. **`_call_llm` 抛错改造**是否同意在 BE-1 + BE-2 合并到一个 PR？（Y/N；建议拆 PR 但 owner 可定）
6. **是否需要**前端 Jobs.tsx 加 degrade 徽标？（Y/N；本期建议不做，UI 改在 v2 评估）
7. **BE-3 宽限期天数**：默认 30 天（PIPL 允许、被盗号可救）是否接受？（Y/N；如 N 请指定 0=立即硬删 或其他天数）
8. **BE-3 优先级**：是否同意与打分链路改造（BE-1/BE-2）同期实施？（Y/N；若对外承诺隐私自主可控的发布在即，建议 BE-3 提到最前）
9. **数据可携权**（PIPL 第 45 条，导出简历+报告 JSON）：本期是否一并做？（Y/N；建议 v2，本期聚焦删除闭环）

## 九、时间线（建议）

```
Day 1:    Task Pack BE-1（白名单护栏）
Day 2-3:  Task Pack BE-2（消除静默降级）
Day 4-5:  Task Pack BE-3（撤回级联清理 + 隐私聚合删除）   ← v1.1 新增
Day 5:    Task Pack QA-1（黄金评测集 + CI 集成，可与 BE-3 并行）
Day 6:    Task Pack FS-1（部署对齐 + 可观测性）
Day 6+:   owner 验收 → 三端上线 → PR 合入 main
```

并行可能性：QA-1.1 黄金集数据准备可与 BE-1 并行；FS-1 可在 Day 5 起并行；BE-3 若 owner 定最高优先级（评审项 #8 选 N），可提前到 Day 1-2 并行 BE-1。

## 十、与历史文档的引用

- 本方案是 `tatha_本地化LLM打分三模型对比与产品化建议_20260921.md` 的下游（模型分级结论的可执行化）
- 本方案是 `looma-zervi_境内DEPLOY_REGION修复与paid订单护栏_20260919.md` 的并行（不打乱现有部署链路）
- 不涉就业合同：`PlanetX-T空间_项目组落地执行方案.md` 是 6 月的设想，本方案是实测收敛后的实操版本

## 十一、待 owner 反馈

请回复 §八 的 9 项 yes/no 决策 + §九 时间线是否接受。owner 拍板后转 ADR 通道开 PR。