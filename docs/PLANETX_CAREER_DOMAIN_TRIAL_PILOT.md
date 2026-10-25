# 职业域 → SaaS 试用试点

> 状态：本地已走通 · 2026-10-25
> 范围：只接 Navigator 六域里的职业域。另外五域先不要照抄按钮。
> 关联：[CN_TO_OVERSEAS_UPGRADE_CONTRACT.md](./CN_TO_OVERSEAS_UPGRADE_CONTRACT.md) · [PLANETX_GROWTH_LOOP_REDESIGN.md](./PLANETX_GROWTH_LOOP_REDESIGN.md)

职业域叙事走完后，页面给出「看这一域的完整职业解读」。点击进入 T-space 定价页，地址带上地区、来源、域和裂变码。试用开通记在同一张码上。传播人数和星际等级都不因这次点击改变。

## 已验证的链路

本地 PlanetX `5173`、SaaS `5174`、looma `5200`（临时 SQLite，`PAYMENT_STUB_MODE=true`，`DEPLOY_REGION=CN`）。

1. 带 `region=CN` 与 `ref` 进入 PlanetX，注册并核销裂变码。
2. 从身份页进入 `/tspace`，地区查询保留。
3. 走完职业域（含诗域回声的两处选择）。完成页出现试用入口，旁边仍是原来的体验反馈。
4. 入口地址为 `http://localhost:5174/pricing?src=planetx_domain&domain=职业域&region=CN&campaign={裂变码}`。
5. 未登录时点「开始 7 天试用」，注册页和登录页都保留上述查询；登录后回到同一张定价页。
6. 定价为契约里的大陆价格：免费 ¥0、支持者 ¥29/月、专业版 ¥99/月。Stub 横幅可见。
7. 开通后页面显示「已开通 Pro 试用（内测 Stub，无需真实支付）」。

事件（同一张裂变码）：

| 事件 | 来源 | 关键字段 |
|---|---|---|
| `trial_clicked` | 浏览器 | `src=planetx_domain`，`domain=职业域`，`region=CN`，`campaign`，`from_planetx=true` |
| `trial_started` | 服务端 | 同上，并有 `from_tier=free` |
| `tier_activated` | 服务端 | `from_planetx=true` 与同一张 `campaign` |

开通的是走完职业域的那个账号，档位变为 `pro`。邀请人仍是 `free`，`spread_count` 仍是 0，双方经验与星际等级都仍是 0 / Lv.1。裂变码当时已有核销记录；试用点击没有再添一条，也没有改传播计数。传播计数只在被邀请人完成人格测试时增加，这是另一条账。

## 查询约定

| 参数 | 值 |
|---|---|
| `src` | 固定 `planetx_domain` |
| `domain` | 本试点只接受 `职业域` |
| `region` | `CN` 或 `US`；`SG` 按 `US` 计价 |
| `campaign` | PlanetX 的 `ref`，4–32 位字母数字。没有就省略 |

`campaign` 存在 `sessionStorage` 的 `planetx_campaign_ref`。核销成功后 `planetx_pending_ref` 会被清掉，不能再拿它拼试用链接。

SaaS 把这组查询记在 `saas_planetx_trial`。未登录点试用时转到 `/register?from=pricing&...`，登录成功回到 `/pricing`，避免归因在注册页丢掉。

服务端只在 `src=planetx_domain` 且 `domain=职业域` 时写入 `from_planetx`。其它域或其它来源的开通不会被记成这条试点。

## 职业域能走完，靠的是选择修正

职业域是唯一的跨域路径：第 3 步是本域选择，第 7 步是诗域选择。引擎两步都要求先选择才能继续。改之前，页面只把第 7 步当成选择，第 3 步的点击被丢掉，诗域选项又因为沿用了第 3 步的选中状态而不可点。职业域因此走不到完成页。

现在两步都能选，选中状态各自记住。单域路径的第 3 步选择保持原样。

## 后续五域怎么扩

每一域自己走完再给自己的出口，不要等六域对照表。对照表仍是「六域都走过」之后的设计验证，不是订阅入口。

扩展时改三处，并保持域名与 Navigator 六域一致（职业、身份、诗、信任、自我、迷雾）：

1. 完成条件从「当前域是职业域」放宽到允许的域名单。
2. 定价页和 `tier_activated` 接受同一名单。问询引擎里的另一组「学习 / 生活 / 社交 / 健康 / 创意」不要写进 `domain`。
3. 事件里的 `domain` 用刚走完的那一域，`campaign` 仍是同一张裂变码。

不要在扩展时把星际等级当成试用资格，也不要按等级改价。

## 这次明确不做

- 不把传播人数换成 `supporter` / `pro`。满 5 人仍只解锁广域扫描。
- 不改经验公式。后端平方根与前端 1.5 倍余量仍是两套等级，称号也仍有两套。试用成功不调用 `addXP`，不调用 `mission-complete`。
- 不读资料卡上的 `level`。那里是 Free / Silver / Gold，不是星际等级。
- 「7 天试用」仍是定价页文案。Stub 开通没有到期，也没有到期回退。本地只能证明「点了、记上了、档位变了」。
- 不实现 `POST /v1/auth/upgrade/issue` 和 `tspace.genz.ltd/upgrade?token=`。那是跨区账号绑定，本试点用带参定价页先把漏斗拉通。
- 落点不是 `app.genz.ltd`。本地落点是 SaaS 的 `/pricing`。
- 5173 与 5174 不共享 `localStorage`。同一个人要在定价页再登录一次，归因靠查询参数，不靠把令牌放进地址。
