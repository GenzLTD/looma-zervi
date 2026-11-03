# 多端支付接入缺口（2026-11-02，Mac / Win 联合补齐后测试）

- 记录日期：2026-11-02
- 交接：Mac 源码核对。Win 补后端与 Web 时以本文为清单，补完后按 §4 一起测。
- 契约真源：`backend/contracts/payment.v1.json` **1.1.0**。大陆渠道只有 `wechat`、`huawei_iap`。支持者版 29 元，专业版 99 元。
- `PAYMENT_LAUNCH_PLAN.md`（2026-09-02）里的「CN ¥9.9/¥29.9」已过期，联测以契约 29/99 为准。
- 收款主体：深伯乐对公账户。商户类目按软件会员报「门户论坛/网络广告及推广/软件开发/其他互联网服务」（支付宝侧为「网络通讯—软件开发服务」B0121）。不要报就业信息平台或求职招聘。

## 1. 已经接通，联测时只回归

| 能力 | 位置 | 现状 |
|---|---|---|
| 微信按订单动态码 | `POST /v1/payment/wechat/order`，默认 `trade_type=NATIVE`，响应 `qr_code_url` | 后端已实现。stub 码为 `weixin://wxpay/stub/<单号>` |
| 微信小程序内下单参数 | 同一接口 `trade_type=JSAPI`，响应 `jsapi_params` | 后端已实现。stub 返回 `paySign=STUB_SIGNATURE` |
| 支付结果 | `POST /v1/payment/wechat/notify`；stub 用 `POST /v1/payment/wechat/notify-simulate` | 验签与模拟核销都在 |
| Web 扫码收银 | `frontend/packages/saas/src/features/pricing/Pricing.tsx` | 已调 `wechatOrder({ trade_type: "NATIVE" })` 并渲染二维码 |
| 华为客户端验签发货 | `POST /v1/payment/huawei/notify`（`huawei_iap_routes.py`） | 已实现 |
| 小程序支付客户端 | `planetx-miniprogram` `createPaymentApi().wechatOrder` | 方法在，定价页未调用 |

订单落 `orders`，字段含 `qr_code_url`。大陆微信单被区域闸限制为 `region=CN`。

## 2. 缺失，补齐前不能当作多端已开通

| # | 缺口 | 证据 | 补齐方 | 补齐后才测 |
|---|---|---|---|---|
| G1 | 小程序定价页关闭支付 | `pages/pricing/index.ts` 中 `PAYMENTS_CLOSED = true`，且写明不走 `requestPayment` | 小程序仓 | JSAPI：下单 →（stub 不拿假签名调起微信）→ `notify-simulate` → `GET /v1/payment/status` 档位变化 |
| G2 | 鸿蒙运行时没有支付调用 | 页面无 `wechatOrder` / IAP。正在使用的 `shared-core/apiRoutes.ets` 只有微信五条路由，没有华为 IAP。`paymentApi.ets` 和华为路由只在 `shared-core-mirror` | 鸿蒙仓 | 应用内会员走 `POST /v1/payment/huawei/notify`。`verify` 仍是 501，不作为通过条件 |
| G3 | 华为服务端向华为查单未做 | `POST /v1/payment/huawei/verify` 固定 501 | 后端 | 有 AGC 凭证后再测。此前只测 notify |
| G4 | iOS 只有展示价，没有下单 | `App/APIClient.swift` 的 `cnDisplayPlans`（29/99）。无 StoreKit，无 `/v1/payment/wechat/order` | iOS 仓 + 契约 | 数字会员必须走 Apple IAP。契约 1.1.0 没有 `apple_iap`，looma 没有 `/v1/payment/apple/*`。小程序 `routes.ts` 里的 apple 路径没有后端 |
| G5 | 支付宝无接入点 | `payment.v1.json` 与 looma 后端都没有 `alipay` | 先改契约再写代码 | 未加入契约前，不测支付宝，也不要把支付宝款记进微信订单 |

固定商家码（不带订单号的那张码）没有、也不该做成接口。会员费用 G 表里已有的微信 NATIVE 动态码，一笔会员一个 `out_trade_no`。

经营类目、对公结算账户是商户平台开户资料，代码里没有字段。开户完成前，实单测试停在 stub。

## 3. 不要补错的通道

- 小程序在 iOS 微信里卖会员，普通 JSAPI 不行，要微信小程序虚拟支付。G1 的 JSAPI 只覆盖安卓微信和开发者工具里的调起链路。
- 鸿蒙应用内会员走华为 IAP（G2/G3），不在元服务里嵌一张微信收款码代替。
- iOS App 不接微信 NATIVE、不接支付宝当面付。
- 支付宝企业收款码若以后要做，只用于自有网页或线下一次性服务费，并单独增加 provider。它不替代 G1/G2/G4。

## 4. 补齐后的联合测试

凭证未到时只做 stub。`PAYMENT_STUB_MODE=true`。实单沿用 `PAYMENT_LAUNCH_PLAN.md` §5：商户六件套、`PAYMENT_STUB_MODE=false`、回调 `POST /v1/payment/wechat/notify`。

### 4.1 现在就能回归（不依赖缺口补齐）

- [ ] Web：登录 → 定价页 NATIVE 下单 → 看到 `weixin://wxpay/stub/` → `notify-simulate` → `orders.status=paid` → `/v1/payment/status` 为 supporter 或 pro，金额 29 或 99
- [ ] 同一单再投递一次 notify，结果仍是已支付
- [ ] `region=US` 调微信下单返回 403

### 4.2 G1 小程序合入后

- [ ] `PAYMENTS_CLOSED` 改为打开后，安卓微信或开发者工具能走到 JSAPI 下单
- [ ] stub 的 `jsapi_params.paySign` 为 `STUB_SIGNATURE` 时，不调用 `wx.requestPayment`
- [ ] `notify-simulate` 之后，该微信用户档位与 Web 同一套 `orders` / tier
- [ ] iOS 微信内卖会员：虚拟支付未接通前，页面保持不可付

### 4.3 G2 鸿蒙合入后

- [ ] 会员购买把华为购买数据送到 `POST /v1/payment/huawei/notify`，验签通过后档位变化
- [ ] `POST /v1/payment/huawei/verify` 在 G3 完成前仍为 501，客户端不依赖它发货

### 4.4 G4 iOS

- [ ] 契约仍是 1.1.0 时：iOS 只展示 29/99，不请求 `/v1/payment/plans?region=CN`（线上该查询 403）
- [ ] 契约写入 `apple_iap` 且验单接口合入后：沙盒购买 → 验单 → 同一用户 tier 变化。未合入前此项不测

### 4.5 商户号到位后的实单（微信）

- [ ] 商户主体为深伯乐，结算账户为对公账户，类目为软件开发 / 其他互联网服务
- [ ] 0.01 元或契约金额的 NATIVE：扫动态码 → 微信回调 notify → `paid`
- [ ] 不使用个人码，不使用无订单号的固定商家码给会员入账

### 4.6 支付宝

- [ ] G5 未合入：确认各端都没有支付宝下单入口
- [ ] G5 合入后另写用例。本清单不把它算进微信实单通过条件
