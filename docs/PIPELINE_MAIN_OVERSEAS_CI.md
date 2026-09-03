# 三条流水线定位说明：main Deploy / Deploy Overseas / PR CI

> **版本：** 1.0 · **日期：** 2026-08-08  
> **受众：** 产品 / 工程 / 运维  
> **关联：** [DUAL_TRACK_ACCEPTANCE_CHECKLIST.md](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md) · [OVERSEAS_DEPLOY.md](./OVERSEAS_DEPLOY.md) · [CN_TO_OVERSEAS_UPGRADE_CONTRACT.md](./CN_TO_OVERSEAS_UPGRADE_CONTRACT.md) · [INTERNAL_TEST_READINESS.md](./INTERNAL_TEST_READINESS.md)

---

## 0. 先纠正一个常见误解

Actions 列表里同时出现三条「全绿」，**并不等于三条都在做部署**。

| 列表上常见标题 | 实际 Workflow | 本质 |
|----------------|---------------|------|
| Merge pull request #N …（`main`） | **Deploy** | **境内部署**（腾讯云） |
| feat: …（`feat/timeline-phase1` 等） | **CI** | **合并前门禁**（测过即可，不写生产机） |
| feat(ui,…（`overseas-vX.Y.Z` tag） | **Deploy Overseas** | **海外部署**（Vultr） |

截图里若看到 `feat/timeline-phase1` 全绿，那是 **PR CI #32**，不是「timeline 环境又部署了一套」。  
`feat/timeline-phase1` 合入 `main` 之后，真正把代码送到内测机的是上面的 **Deploy #73**。

**一句话：** CI 证明「能不能合」；Deploy / Deploy Overseas 证明「合了之后落到哪台机器」。

---

## 1. 三条流水线总览

```text
                    ┌─────────────────────────────────────┐
  开发分支 push     │  PR → CI（typecheck / unit / e2e…）   │  ← 质量门禁，不部署
  开 PR 到 main     └──────────────────┬──────────────────┘
                                       │ 全绿 + 人工合入
                                       ▼
                    ┌─────────────────────────────────────┐
  push main         │  Deploy → 腾讯云 1.14.202.161         │  ← 境内产品线
                    │  PlanetX + T-space + API              │
                    └─────────────────────────────────────┘

  另线发版（打 tag）
                    ┌─────────────────────────────────────┐
  overseas-* tag    │  Deploy Overseas → Vultr SG           │  ← 海外产品线
                    │  API + SaaS(tspace)                   │
                    │  营销站 genz.ltd 由 Vercel 独立仓      │
                    └─────────────────────────────────────┘
```

| 维度 | **CI**（如 timeline PR） | **Deploy**（main） | **Deploy Overseas**（overseas-*） |
|------|--------------------------|--------------------|-----------------------------------|
| Workflow 文件 | `.github/workflows/ci.yml` | `.github/workflows/deploy.yml` | `.github/workflows/deploy-overseas.yml` |
| 触发 | PR → `main`（打开/同步） | `push` 到 `main` | `push` tag `overseas-*`（或手动） |
| 是否写远端机器 | 否 | 是 · 腾讯云 | 是 · Vultr 新加坡 |
| 产品主叙事 | 「这批改动可合并」 | 微信生态裂变底座（Web+API） | 海外直达 SaaS + 收银 API |
| 与获客策略 | 护栏 | **境内线第一步** | **海外线主发布** |

---

## 2. CI（示例：feat/timeline-phase1）

### 2.1 定位

**合并前质量闸门。**  
任何准备进 `main` 的 PR（含曾经的 `feat/timeline-phase1`）都应在此跑通：前端类型检查、单测、后端测试、Live E2E、Docker 构建检查等。

### 2.2 价值

- 挡住坏提交进入主干，避免 Deploy 把半成品推上内测机  
- 给「能不能合」一个客观信号（全绿 ≠ 产品已上线，只表示工程可合并）  
- 与部署解耦：CI 失败时不应靠「再部署一次」碰运气  

### 2.3 不是什么

- **不是**第三条业务环境  
- **不是**海外或境内的正式发布通道  
- PR 合并后，该分支上的 CI 记录会留在历史里；**线上状态以 main / overseas tag 的 Deploy 为准**

### 2.4 和另外两条的关系

```text
CI 全绿 ──允许──► 合入 main ──触发──► Deploy（境内）
                      │
                      └── 代码进入主干后，若再打 overseas-* tag
                              ──可触发──► Deploy Overseas（海外）
```

同一批功能可以：先 CI → 合 main（境内部署）→ 日后在合适 tip 上打 `overseas-v*`（海外部署）。  
**合 main 不会自动跑 Deploy Overseas**；**打 overseas tag 也不会自动更新腾讯云**。

---

## 3. Deploy（main · 境内）

### 3.1 定位

**大陆产品内测/准生产发布通道。**  
`main` 一有实质代码 push（文档-only 变更可被 `paths-ignore` 跳过），就部署到腾讯云默认机 `1.14.202.161`：

| 路径 | 产物 |
|------|------|
| `/` | PlanetX Web |
| `/tspace/` | T-space（SaaS） |
| `/v1/` | Looma API（Docker :5200） |

**刻意不部署：** genz.ltd 营销站、Bolent 企业站、Vultr 海外面。

### 3.2 价值（在双轨策略里）

境内获客主叙事是 **微信生态裂变**，不是营销站直达 SaaS：

1. **合 main → Deploy** = 给小程序 / PlanetX Web 提供公网 API 与 Web 辅入口  
2. 裂变玩法（邀请、传播计数、匹配共识、信任档案等）先在这台机器上可验收  
3. 小程序体验版/上架后，请求打到同一套境内 API，才形成规模化关系链增长  

因此：**Deploy 全绿 =「境内底座已刷新」**，是微信裂变的工程第一步，不是裂变已经完成。

### 3.3 仍未自动完成的事

- 小程序体验版联调与**正式上架**  
- 微信合法 request / 业务域名配置  
- 备案域名切换（当前常见为 IP 模式 `DEPLOY_NGINX_MODE=ip`）  
- 微信支付实付（可仍为 Stub）  

### 3.4 典型成功信号

Actions：**Deploy** · branch `main` · 由 merge PR 触发 · 结论 success。  
例：`Merge pull request #8 …` · Deploy #73 · `d89aab6`。

---

## 4. Deploy Overseas（overseas-* · 海外）

### 4.1 定位

**海外产品发布通道（与 main 分轨）。**  
由 tag `overseas-*`（或 `workflow_dispatch`）触发，部署到 Vultr 新加坡，域名面大致为：

| Host | 角色 |
|------|------|
| `api.genz.ltd` | 海外 API |
| `tspace.genz.ltd` | 海外 SaaS（注册/工作台） |
| `genz.ltd` | 营销站（**独立仓 Vercel**，本 workflow **不**发布 genz-web） |

CI 契约约定营销 CTA：`appRegisterUrl = https://tspace.genz.ltd/register`。

### 4.2 价值（在双轨策略里）

海外获客逻辑与境内不同：**倾向直达 SaaS**，少游戏化中间层。

```text
genz.ltd（信任 / 法律 / 定价）
    → tspace.genz.ltd/register（SaaS）
    → api.genz.ltd（Google / Stripe 等）
```

- **Deploy Overseas 全绿** = 海外 API + SaaS 已按该 tag 刷新  
- 营销站是否同步，看 genz-web 仓 / Vercel，不看本仓库 Deploy  
- `app.genz.ltd`（海外 PlanetX）是可选副线，**不是**海外主漏斗必选项  

### 4.3 与 main Deploy 的硬差别

| | Deploy（main） | Deploy Overseas |
|--|----------------|-----------------|
| 触发物 | 分支 `main` | tag `overseas-*` |
| 机器 | 腾讯云 | Vultr SG |
| 前端重点 | PlanetX + SaaS 同机 | **SaaS 为主**（+ API） |
| 登录/支付取向 | 微信生态 | Google / Stripe |
| 获客 | 裂变（小程序为主） | 营销 → 注册 |

两套环境 **JWT / 用户库 / 支付真源均分轨**，不能假设「main 部署成功 = 海外已更新」。

### 4.4 典型成功信号

Actions：**Deploy Overseas** · 黄色 badge 为 tag（如 `overseas-v3.1.6`）· 结论 success。

---

## 5. 「三个都全绿」到底意味着什么

以 2026-08-08 前后一次常见列表为例：

| 条目 | 含义 |
|------|------|
| Deploy · main · PR #8 merge | **境内机已吃到合入后的主干**（PlanetX Web + API + T-space） |
| CI · feat/timeline-phase1 | **该 PR 合入前的检查曾通过**（历史门禁记录） |
| Deploy Overseas · overseas-v3.1.6 | **海外机已按该 tag 发布过**（与本次合 main **无自动因果关系**） |

合在一起说明：

1. 主干质量门禁走过，且境内已发布 —— **境内内测/裂变底座可用**  
2. 海外线在最近一次 tag 上也是健康的 —— **海外直达 SaaS 通道可用**  
3. 二者 **并行健康**，不是「一条流水线部署了三个环境」

**不等于：**

- 小程序已上架或裂变已放量  
- 海外 Stripe/Google 业务验收已全部签字  
- timeline 另有独立生产集群  

---

## 6. 产品价值对照（双轨获客）

| 战略 | 主通道 | 对应流水线 | 全绿后的产品含义 |
|------|--------|------------|------------------|
| **境内** | 微信小程序裂变 + PlanetX 辅 | **Deploy（main）** + 日后小程序发版 | 公网 API/Web 就绪，可体验版验闭环 |
| **海外** | 营销站 → SaaS 注册 | **Deploy Overseas** + Vercel 营销仓 | 访客可直达 `tspace` 注册与 API |
| **工程护栏** | 任意进主干的改动 | **CI** | 降低把坏构建推上境内机的概率 |

跨线（国内裂变用户升级出海收银）见 [CN_TO_OVERSEAS_UPGRADE_CONTRACT.md](./CN_TO_OVERSEAS_UPGRADE_CONTRACT.md)；那是账号/付费契约，**不是**第三条 Deploy。

---

## 7. 日常怎么读 Actions 列表

1. 看 **Workflow 名称**（Deploy / Deploy Overseas / CI），不要只看 commit 标题  
2. 看 **badge**：`main` = 境内发布；`overseas-v*` = 海外发布；`feat/*` = 通常是 CI  
3. 要验证境内：打开腾讯云 PlanetX / `/health`，对一下 Deploy 的 commit  
4. 要验证海外：打开 `tspace.genz.ltd/register` + `api.genz.ltd/health`，对一下 overseas tag  
5. 需要海外发版时：**先保证目标 commit 在远端，再只推 tag**，避免与分支 push 混淆  

---

## 8. 一句话备忘

| 流水线 | 一句话 |
|--------|--------|
| **CI** | 证明「这批代码配进 main」 |
| **Deploy（main）** | 把主干送到腾讯云，服务境内裂变底座 |
| **Deploy Overseas** | 把指定 tag 送到 Vultr，服务海外直达 SaaS |

三条全绿 = **门禁 + 境内发布 + 海外近期发布都健康**；继续推进境内裂变时，下一步重点在小程序体验版/上架，而不是再找第四条「timeline 部署」。
