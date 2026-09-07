# PAYMENT_LAUNCH_PLAN — 支付上线方案（双通道）

- 状态：**方案已定稿，Phase A 本地验收通过（247 passed），凭证后补执行**
- 双仓同步：本文档 = `looma-zervi/docs/PAYMENT_LAUNCH_PLAN.md` = `szbolent-portal/docs/PAYMENT_LAUNCH_PLAN.md`
- 相关文档：`COMMERCE_CLOSURE_STATUS.md`、`PAYMENT_TIER_CONTRACT.md`、`OVERSEAS_DEPLOY.md`、`DEPLOY_OVERSEAS_SETUP.md`（looma 侧）；`OPERATIONS_MANUAL.md`（szbolent-portal 侧）
- 日期：2026-09-02

## 0. 结论与路径

双通道都要：先 Phase A（本地验收，已完成），再按凭证到位顺序上实单（Stripe 海外 → 微信境内）。
凭证后补执行：Phase A + 代码修复（R1 本仓）可先行，Phase B-1/B-2 的每一大步都有「凭证闸门 + 验收点」，凭证到了逐项勾。

```
Phase A 本地验收（✅ 已完成 247 passed）
  → R1 region 修复（✅ 见 §3，本仓代码）
  → 三端代码同步 + stub=true 冒烟（凭证前唯一可推进的上实网动作）
  → Phase B-1 Stripe test → live（Vultr，等 sk_live/whsec_）
  → Phase B-2 微信实单（天翼，等商户 6 件套 + HTTPS 回调域）
  → 上线后检查（对账/日志/降级预案）
```

## 1. 代码真源（勿按旧手册猜路径/键名）

| 项 | 真源 |
|---|---|
| 定价/区域 | `backend/src/payment/plans.py`：`SUPPORTED_REGIONS={CN,US}`、`DEFAULT_REGION=CN`、`DEPLOY_ALIASES={SG:US}`；`resolve_region` 只认 query `region` + `Accept-Language`（zh*→CN，其他非空→US） |
| 契约 | `backend/contracts/payment.v1.json`（CN ¥9.9/¥29.9 微信；US $1.99/$5.99 Stripe） |
| Stripe 端点 | `POST /v1/payment/stripe/checkout`、`POST /v1/payment/stripe/webhook`（`src/api/routes/payment_routes.py`） |
| 微信端点 | `POST /v1/payment/wechat/order`(JSAPI/NATIVE)、`POST /v1/payment/wechat/notify`（RSA 验签，`wechat_pay.py`）；**路径是 `/wechat/notify`，不是旧手册 `/notify/wechat`** |
| 统一入口 | `POST /v1/payment/checkout`、`POST /v1/payment/webhook/<provider>`（providers 抽象，见 `src/payment/providers/`） |
| 华为 IAP（CN 元服务支付通道） | `POST /v1/payment/huawei/notify`，启用依赖 `HUAWEI_IAP_PUBLIC_KEY` |
| 凭证键名（`backend/.env`） | `WECHAT_MCHID / WECHAT_API_V3_KEY / WECHAT_SERIAL_NO / WECHAT_PRIVATE_KEY_PATH / WECHAT_NOTIFY_URL`（**无 `PAY` 中缀**）；`STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET` |
| 依赖 | `backend/requirements.txt` 已含 `cryptography>=42` 与 `stripe>=8`；Dockerfile `COPY requirements.txt` 全量安装 |
| stub 门控 | `PAYMENT_STUB_MODE` 默认 true；true 时 upgrade 走 stub、真支付端点 400/501；**漏改 false = 静默不收钱** |

## 2. 目标环境矩阵

| 端 | 地址/角色 | 编排 | 目标状态 |
|---|---|---|---|
| Vultr SG | 139.180.184.25（genz.ltd 海外站 + 海外 Looma） | docker compose，backend :5200 公网，宿主 nginx | Stripe 收银（US 定价）；`api.genz.ltd/v1/` 已是入口 |
| 天翼 | 14.29.216.219（gfcc 全栈主战斗 + looma-backend :5203 内网） | `docker-compose.tianyi.yml`；nginx `/v1/`→5203 | CN 区收银（微信 JSAPI/NATIVE）；需一个 HTTPS 域指到天翼 nginx 收微信回调 |
| 腾讯 | 1.14.202.161（QCC 网关 + 大陆 Looma，PlanetX dist 同机） | docker compose :5200 | CN 获客 Looma；本迭代不动支付 |
| 本机 | 开发环 :5200 | `./dev.sh` | Phase A 测试场 |

部署方式：容器 `/app` 是 `../backend` bind mount → **同步代码 + `docker compose restart backend` 即生效，无需 rebuild**（镜像首次已 build；若早期镜像缺新依赖才需手动 rebuild 一次）。

## 3. 上线前代码修复（R1，本仓已提交）

### R1 — region 决策修复（`backend/src/payment/plans.py`）
- 症状：Vultr 部署脚本把 `.env` 写 `DEPLOY_REGION=SG`（`.env.example` 默认 `US`），**但代码零消费该键**（`src/config.py` 无引用，死配置）；定价区域唯一决策点 `resolve_region` 对「显式 `region=SG`」与「非 zh/en 的 Accept-Language」都落 `CN/CNY` → 海外端会拿微信人民币方案走 Stripe 集成，必错。
- 修复（2026-09-02）：`normalize_region` 增加部署位别名 `DEPLOY_ALIASES={SG: "US"}`（未知码仍回 `CN`，保持既有测试语义）；`resolve_region` 非 zh 语言一律兜底 `US`（原：非 zh/en 落 CN）。
- 新增用例：`?region=SG → US/USD/stripe`；`Accept-Language: de-DE → US`；`?region=XX → CN`（保留）。
- 接线要求：海外前端仍应显式传 `region=US`（或依赖 en Accept-Language），不靠兜底。

## 4. Phase B-1 Stripe（海外，凭证后补）

凭证闸门：Stripe live `sk_live_*` + webhook `whsec_*`（test 用 `sk_test_*` 先行）。

步骤：
1. `cd /opt/looma-zervi`（Vultr）同步代码到 SG 分支 → **先 `cp backend/.env backend/.env.bak`**（deploy-overseas.sh 重跑会 sed 覆盖 `DEPLOY_REGION=SG`/`LLM_PROVIDER_ORDER`，不会碰 Stripe，但别赌）
2. 编辑 `backend/.env`：`PAYMENT_STUB_MODE=false`；`STRIPE_SECRET_KEY`、`STRIPE_WEBHOOK_SECRET`；核对 `STRIPE_SUCCESS_URL/STRIPE_CANCEL_URL`（脚本已自动追加）
3. Stripe Dashboard → Webhooks → endpoint `https://api.genz.ltd/v1/payment/stripe/webhook`，订阅事件：`checkout.session.completed`、`checkout.session.async_payment_succeeded`、`checkout.session.async_payment_failed`、`invoice.paid`、`invoice.payment_failed`、`customer.subscription.updated`（6 事件，HK 指南 §3.3 口径）
4. 确认 Stripe 产品 price_id 与契约对齐（$1.99 / $5.99 月付）
5. `cd docker && docker compose restart backend`
6. 验收（test 先行，全通再 live）：
```bash
curl -sf https://api.genz.ltd/health
curl -s "https://api.genz.ltd/v1/payment/providers?region=US" | jq '{stub_mode, provider: .payment_provider}'
# 测试卡 4242 走 checkout → webhook 落单 → 用户 payment status 显示 paid + tier/expires_at
```
7. 回归：`POST /v1/payment/upgrade` 仍应 402（不可绕过 stub 门控语义）

## 5. Phase B-2 微信支付（境内，凭证后补）

凭证闸门：微信商户号 6 件套（`WECHAT_MCHID/API_V3_KEY/SERIAL_NO/PRIVATE_KEY_PATH`）+ 小程序绑定 `WECHAT_APPID` + **HTTPS 回调域**（代码真源 `/v1/payment/wechat/notify`）。

前置选型（唯一未拍板项）：天翼 looma nginx 需要一个公网 HTTPS server 反代 `/v1/payment/wechat/notify`→5203。
- 选项 A：`api.szbolent.com.cn`（企业备案域，规划中，需先有域名）
- 选项 B：给天翼 nginx 挂 `circle.genz.ltd` 或新子域反代 `/v1/`（circle-genz 现只反代 `/circle/`→5211）
微信商户平台要求回调域名与小程序一致且可公网验证，二选一后同步改 `WECHAT_NOTIFY_URL`。

步骤：
1. 同步代码到天翼 `/opt/looma-zervi`（先备份 .env）
2. `backend/.env` 填商户 6 件套；`WECHAT_PRIVATE_KEY_PATH` 指向容器内 `/secure/apiclient_key.pem`（证书落宿主 `/secure/`，勿入 git）；`WECHAT_DEV_MODE=false`；`PAYMENT_STUB_MODE=false`
3. 商户平台登记回调 `https://<所选域>/v1/payment/wechat/notify`
4. 本机回归 `venv/bin/python -m pytest tests/test_payment_notify.py tests/test_payment_jsapi.py`（验签/幂等已覆盖）
5. 0.01 元实单：NATIVE 下单 → 扫码支付 → notify → `orders.status=paid` → 用户 tier 升、`/v1/payment/status` 返回新 expires_at
6. 幂等重放：同 notify 体重放一次应幂等成功（测试已覆盖，实网抽查一次）

## 6. 执行 Checklist（凭证后补逐项勾）

| # | 动作 | 目标端 | 凭证/前置 | 状态 | 证据 | 日期 |
|---|---|---|---|---|---|---|
| 1 | Phase A 本地验收（支付 7 套 56 + 全量 247） | 本机 | 无 | ✅ | pytest 输出 | 2026-09-02 |
| 2 | R1 region 修复 + 用例 | 本机 | 无 | ✅ | `plans.py` + 测试全绿 | 2026-09-02 |
| 3 | 代码同步 + restart，stub=true 冒烟 | Vultr / 天翼 | 无 | ✅ | `plans?region=SG→US/USD/stripe`；providers `stub_mode:true` | 2026-09-02 |
| 4 | 云端 cryptography 自检 | Vultr / 天翼 | 无 | ✅ | Vultr 49.0.0 / 天翼 50.0.0（requirements 已含，无 rebuild） | 2026-09-02 |

### 伺服执行记录（2026-09-02，凭证未配前提下的全部可推进项）

- R1 `plans.py` 已 scp 同步两端（Vultr 非 git 树走文件覆盖；天翼 git 树 d7d92db 出现未跟踪 M，属预期）+ `docker restart looma-backend` 生效
- 复验：Vultr 公网 `api.genz.ltd/v1/payment/plans?region=SG` → `USD/stripe/paypal/airwallex`（原 CNY/wechat，R1 修复实证）；天翼 :5203 同
- `PAYMENT_STUB_MODE`：Vultr `.env` 原缺该键（config 默认 true 兜底，安全），已显式补 `true` 防未来默认翻转；天翼 `.env` 原 `true` 不变
- stub 门控线上冒烟：`GET /v1/payment/providers?region=US|SG` → `{"providers":[],"stub_mode":true}`（凭证未配 = 无 provider + 真支付端点 400，不静默收钱）
- cryptography 容器内自检通过（见 #4）；镜像无需 rebuild
- 腾讯端（1.14.202.161）按 §2「本迭代不动支付」未动；其 R1 代码同步为非阻塞尾巴
| 5 | Stripe test 卡全流程 | Vultr | sk_test + whsec_test | ⬜ | checkout→webhook→paid | |
| 6 | Stripe live 切换 | Vultr | sk_live + whsec_live | ⬜ | 4242 live 单 | |
| 7 | 回调域选型落地 | 天翼 | HTTPS 域 | ⬜ | nginx 反代 5203 `/v1/` | |
| 8 | 微信 0.01 元实单 | 天翼 | 商户 6 件套 | ⬜ | NATIVE→notify→paid | |
| 9 | 上线后监控/对账 | 两端 | 无 | ⬜ | 日志 + 日对账 | |

## 7. 风险与坑

- `deploy-overseas.sh` 重跑 sed 覆盖 `DEPLOY_REGION=SG`/`LLM_PROVIDER_ORDER` → **重跑前备份 .env**
- `PAYMENT_STUB_MODE` 默认 true；漏改 false = 静默不收钱（上线核对第一项）
- `DEPLOY_REGION` 是死配置（代码零消费）：不要靠它判断计价区域，region 决策只认 plans 层；R1 已加 `SG→US` 部署别名
- `cryptography` 已进 requirements；wechat 签名若缺依赖会静默 skeleton fallback（日志找 "skeleton fallback"）
- 微信回调路径真源 `/v1/payment/wechat/notify`（旧手册 `/notify/wechat` 已过时）
- 天翼 `.env` 现挂着 Stripe key 且区域为 CN（契约收款真源应在 SG）——清理或作为 CN 侧测试通道，待拍板
- 腾讯 `/v1/` 直代天翼 `/v1/`：微信 notify 不经腾讯链路（直达天翼 nginx），无影响
