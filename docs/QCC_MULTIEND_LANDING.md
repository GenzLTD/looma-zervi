# QCC MCP 多端落地（2026-11-02，Mac / Win 联合测试）

- 记录日期：2026-11-02
- 交接：Mac 已把企业信用卡片补到小程序、iOS、鸿蒙。Win 联测时按本文，不要让客户端直连企查查。
- 客户端只调 looma。企查查 MCP 只在 `backend/src/credit/qcc_client.py`。生产直连 `https://agent.qcc.com`，不要设置 `QCC_MCP_BASE_URL`。`127.0.0.1:8998` 是本机 nginx 反代，重启即没，不是生产入口。
- 授权范围一律 `credit_query`（文案「企业风险查询」）。未授权先弹同意，同意后 `POST /v1/compliance/consent/grant`。

## 1. 后端，四端共用

| 接口 | 默认数据 | 说明 |
|---|---|---|
| `POST /v1/credit/check-company` | 工商、风险、经营、高管 | 要登录和 `credit_query`。QCC 失败时 `source=llm`，卡片标「AI 参考」 |
| `POST /v1/credit/check-company/detail` | 上面四类，再加知识产权、历史、司法、文书 | 接口在。各端页面都没调用 |

成功时 `source=qcc`。响应含 `extracted`（名称、报告类型、摘要）和 `extended`（企业、风险、经营、高管）。同名企业进程内缓存 24 小时。

当前 token 调历史信息服务返回 `300012 当前用户未授权使用历史信息服务`。股权变更不靠这条，走 company 的 `get_change_records`。detail 里的 history 段可能为空，联测不要把它当失败。

## 2. 已经落到页面

对照 Web SaaS `frontend/packages/saas/src/features/hr/Jobs.tsx` 的单家查询卡片。海外站 `IS_OVERSEAS` 不展示这张卡。

| 端 | 入口 | 调用 | 卡片 |
|---|---|---|---|
| Web SaaS | 职位匹配行上的单家查询 | `creditApi.checkCompany` | 法人、注册资本、成立日期、登记状态、行业、风险、高管、摘要；有 `extended` 时标企查查 |
| 小程序 | 求职页匹配行、求职页职位列表、职位详情 | `creditApi.checkCompany` | `utils/credit-card.ts`，同一组字段。`source=qcc` 或带 `extended` 标「企查查」，否则「AI 参考」 |
| iOS | `JobsView` 的匹配卡和职位卡 | `APIClient.checkCompany` → `POST /v1/credit/check-company` | `CreditSnapshot`，同一组字段。授权弹窗与求职授权分开 |
| 鸿蒙 | 仅职位详情 `JobDetailPage.ets` | 页面直接 `POST /v1/credit/check-company` | 同一组字段。同意文案写明优先企查查、失败可降为 AI 参考 |

四端都不持有 `QCC_AUTH_TOKEN`，也不访问 `agent.qcc.com` 或 `:8998`。

## 3. 客户端有方法、页面未用

| 项 | 现状 | 联测时 |
|---|---|---|
| detail | 小程序 `createMiniApi.checkCompanyDetail`、鸿蒙 `HarmonyApiClient.checkCompanyDetail` 已有。iOS 没有该方法。页面都只调 `check-company` | 不测详情页，除非有人把按钮接上 |
| Web 批量查信用 | `Jobs.tsx` `handleBatchCredit`，仅大陆，匹配结果逐家调用并间隔 300ms | 只在 Web 测 |
| 报告里的 `credit_snapshot` | 仅 Web 保存匹配报告时写入当次查询结果 | 小程序、iOS、鸿蒙没有这条 |
| looma 仓里的小程序客户端 | `frontend/packages/shared-core/src/api/createMiniApi.ts` 只有 `checkCompany` | 小程序真源是 `planetx-miniprogram/packages/shared-core`，那里才有 `checkCompanyDetail` |
| 鸿蒙职位列表 | 列表页没有「查企业信用」 | 从详情页进 |
| 小程序页面测试 | `career` / `job-detail` 的 Jest 当时未跑完（工程里没有 Jest，安装被中止） | 卡片字段用样例响应核对过；页面测试补跑后再勾 |
| 鸿蒙 / iOS 编译 | 这次没有在本环境编译 | 真机或模拟器点按后再勾 |

Cursor 的 `~/.cursor/mcp.json` 里 `mcpServers` 为空。那不是产品链路，联测不要从 Cursor 调企查查。

## 4. 联合测试

用同一家公司名（建议「深伯乐（深圳）科技有限公司」）在四端各查一次。QCC 可用时期望 `source=qcc`，法人许靖涵，统一社会信用代码 `91440300MA5H3GJL4E`。

- [ ] 未授予 `credit_query` 时，四个入口都先要授权，不发查询
- [ ] 授予后，Web、小程序求职页、小程序职位详情、iOS 匹配卡、鸿蒙职位详情各返回一张卡
- [ ] 卡上能看到法人、注册资本、成立日期、登记状态、行业、风险、高管、摘要，来源为企查查
- [ ] 关掉 `QCC_ENABLED` 或抽掉 token 后再查：请求仍 200，`source=llm`，来源标成 AI 参考，不把失败当成接口挂了
- [ ] 生产环境没有 `QCC_MCP_BASE_URL`，后端直连 `agent.qcc.com`
- [ ] 不测 detail、不测小程序/iOS/鸿蒙的批量查询和 `credit_snapshot`，除非 §3 已接到页面
