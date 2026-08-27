# Stripe 香港公司账户注册指南

> **目标**：以香港公司主体注册 Stripe 账户，接入 genz.ltd 海外支付
> **适用场景**：国内个人 + 香港公司主体，做海外 SaaS 收款
> **最后更新**：2026-07-12

---

## ⚠️ 关键提醒（先看这 4 条）

> 以下 4 条是踩坑高发区，注册前务必确认：

**1. 网站必须先上线**
- Stripe 审核员会实际打开 `genz.ltd` 查看内容，空白页或 404 直接拒
- 网站必须包含：产品介绍 + 定价页面 + 服务条款 + 退款政策 + 隐私政策 + 联系方式
- 联系方式用公司域名邮箱（`zervi@genz.ltd`），不要用 Gmail/QQ 邮箱
- 这是审核被拒的第一大原因，**材料齐全但网站没内容 = 白等**

**2. 不要用 VPN / 大陆 IP 注册**
- 注册时使用香港 IP 或其他海外 IP，不要走 VPN
- 大陆 IP 访问 Stripe 可能触发风控，导致注册被限或审核周期拉长
- 如果人在深圳，用香港手机热点或直接在香港操作最稳妥

**3. 手续费 3.4% + HK$2.35/笔 — 定价要算进去**
- 香港地区国际卡费率：**3.4% + HK$2.35/笔**
- 比国内支付渠道高（微信/支付宝约 0.6%），定价时必须覆盖
- 退款不退手续费，只退本金；争议（Chargeback）每笔扣 HK$80
- **定价建议**：Pro 月费至少 $19.99 起，太低的话手续费占比过高不划算

**4. 离岸豁免 — 利得税可降到 0%**
- 香港公司利润 200 万港币以内税率 8.25%，超过部分 16.5%
- 如果客户全在海外（不在香港本地），可向香港税局申请**离岸豁免**
- 申请成功后利得税税率为 **0%**
- 申请条件：利润来源不在香港（客户/运营/合同/谈判都在海外）
- 需要找香港会计师代办，费用约 HK$3,000-8,000，首年做账时一起申请
- **注意**：离岸豁免不是自动的，必须主动申请；申请期间税务局可能来函询问

---

## 一、前置条件确认（逐条打勾）

在开始 Stripe 注册之前，确认以下材料全部就位：

### 1.1 香港公司主体

- [ ] **公司注册证书（Certificate of Incorporation, CR）**
  - 也叫「公司注册证书」，香港公司注册处签发
  - 上面有公司编号（Company Number，8 位数字）
  - 确认公司类型为 Limited（有限公司），Stripe 不接受无限公司

- [ ] **商业登记证（Business Registration Certificate, BR）**
  - 税务局签发，有效期通常 1 年或 3 年
  - 确认在有效期内（过期需先续期）
  - 上面有商业登记号码（BR Number）

- [ ] **公司章程（Articles of Association）**
  - 注册公司时提交的那份，一般不需要额外准备
  - Stripe 可能要求提供，备着

### 1.2 公司银行账户

- [ ] **香港本地银行的公司账户**
  - 支持的银行：汇丰（HSBC）、渣打（Standard Chartered）、中银香港（BOC）、花旗（Citi）、星展（DBS）等
  - 账户名必须跟公司注册英文名一致
  - 需要提供银行账户的月结单（Bank Statement），最近 3 个月内

- [ ] **确认账户能接收 USD 电汇**
  - 香港公司银行账户一般都支持多币种
  - Stripe 默认以 HKD 或 USD 结算，建议选 USD 结算避免汇率损失

### 1.3 董事/负责人信息

- [ ] **董事身份证件**
  - 香港身份证（正反面）或 护照（信息页）
  - 如果董事是中国大陆居民，提供中国大陆身份证 + 护照
  - 护照更优先，Stripe 对护照审核更顺畅

- [ ] **董事住址证明**
  - 最近 3 个月内的水电费账单 / 银行月结单 / 政府信件
  - 地址必须跟填写的居住地址一致
  - 如果是中文账单，Stripe 可能要求翻译件（但不强制）

### 1.4 网站

- [ ] **genz.ltd 首页已上线**
  - Stripe 审核会访问你的网站，确认业务真实
  - 首页需要包含：产品说明、定价页面、联系方式、服务条款链接、退款政策链接
  - 如果只是空白页或 404，审核大概率被拒

- [ ] **定价页面**
  - 列出套餐和价格（USD 计价）
  - 跟你在 Stripe Dashboard 创建的产品价格一致

- [ ] **服务条款（Terms of Service）**
  - 在网站底部放一个链接，指向 `/terms` 或 `/legal/terms`
  - 可以用模板生成，但必须存在

- [ ] **退款政策（Refund Policy）**
  - 在网站底部放一个链接，指向 `/refund` 或 `/legal/refund`
  - Stripe 强制要求

- [ ] **联系页面**
  - 邮箱（建议用公司域名邮箱，如 `zervi@genz.ltd`）
  - 不要用 Gmail / QQ 邮箱作为唯一联系方式

---

## 二、Stripe 注册流程（逐步操作）

### Step 1：访问 Stripe 注册页面

- [ ] 打开 https://dashboard.stripe.com/register
- [ ] 国家/地区选择 **Hong Kong**
- [ ] 不要选 China（中国大陆不支持）

### Step 2：填写账户信息

- [ ] **账户类型**：选「Company / Business」（不要选 Individual）
- [ ] **公司英文名**：跟 CR 上的英文名**完全一致**（包括 Ltd. / Limited 后缀）
- [ ] **公司编号**：CR 上的 8 位 Company Number
- [ ] **注册地址**：香港注册地址（跟 BR 上一致）
- [ ] **营业地址**：如果跟注册地址不同，单独填

### Step 3：填写业务信息

- [ ] **行业分类**：选「Software / SaaS」或「Information Services」
- [ ] **业务描述**（英文）：
  ```
  Genz.ltd is an AI-powered career development platform that provides 
  intelligent job matching, resume optimization, and career planning 
  tools for job seekers worldwide.
  ```
  （根据实际业务修改，不要照抄）
- [ ] **产品 URL**：填 `https://genz.ltd`
- [ ] **Statement Descriptor**：信用卡账单上显示的名称（最多 22 字符）
  - 建议填 `GENZ.LTD` 或公司简称

### Step 4：绑定银行账户

- [ ] 选择 **Bank transfer (HK)** 或 **SWIFT** 方式
- [ ] 填入香港公司银行账户信息：
  - 银行名称（如 HSBC）
  - 账户号码
  - 账户持有人名（公司英文名）
- [ ] 上传银行月结单（最近 3 个月，PDF 或图片）

### Step 5：填写负责人信息

- [ ] **姓名**：跟证件一致
- [ ] **出生日期**
- [ ] **证件类型**：选 Passport（推荐）或 ID Card
- [ ] **证件号码**
- [ ] **居住地址**：当前实际居住地址
- [ ] 上传证件照片（清晰、完整、无遮挡）

### Step 6：提交审核

- [ ] 检查所有信息无误
- [ ] 点击「Submit」
- [ ] 等待邮件确认（通常 1-3 个工作日）

---

## 三、审核通过后的操作

### 3.1 获取 API Keys

- [ ] 登录 Stripe Dashboard
- [ ] 进入「Developers」→「API Keys」
- [ ] 复制 **Publishable Key**（以 `pk_` 开头）
- [ ] 复制 **Secret Key**（以 `sk_` 开头，点「Reveal test key」或「Reveal live key」）

### 3.2 创建产品与价格

- [ ] 进入「Products」→「Add product」
- [ ] 创建 **Free** 产品（用于关联 free 套餐，价格为 $0）
- [ ] 创建 **Pro Monthly** 产品：
  - 名称：`Genz Pro - Monthly`
  - 价格：`$19.99` / month（根据你的定价调整）
  - 计费方式：Recurring
- [ ] 创建 **Pro Yearly** 产品（可选）：
  - 价格：`$199.99` / year
- [ ] 记录每个价格的 **Price ID**（以 `price_` 开头）

### 3.3 配置 Webhook

- [ ] 进入「Developers」→「Webhooks」→「Add endpoint」
- [ ] **Endpoint URL**：`https://api.genz.ltd/v1/payment/stripe/webhook`
- [ ] **事件订阅**（至少勾选以下）：
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
- [ ] 创建后复制 **Signing Secret**（以 `whsec_` 开头）

### 3.4 配置 VPS .env

SSH 到 VPS 后编辑 `.env` 文件：

- [ ] `STRIPE_PUBLIC_KEY=pk_live_xxxxxxxxxxxx`
- [ ] `STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxx`
- [ ] `STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx`
- [ ] `STRIPE_CURRENCY=USD`
- [ ] `STRIPE_WEBHOOK_URL=https://api.genz.ltd/v1/payment/stripe/webhook`

保存后重启后端容器：
```bash
cd /opt/looma-zervi && docker-compose restart backend
```

### 3.5 验证支付流程

- [ ] 用 Stripe 提供的测试卡号 `4242 4242 4242 4242` 跑一笔测试支付
- [ ] 确认 Webhook 收到事件
- [ ] 确认数据库订单记录写入
- [ ] 确认用户套餐状态更新

---

## 四、注意事项

### 4.1 审核相关

| 注意点 | 说明 |
|--------|------|
| **网站必须能访问** | Stripe 审核员会实际打开 genz.ltd 看内容，空白页直接拒 |
| **信息一致性** | 填写的公司名、地址、董事信息必须跟 CR/BR/证件完全一致 |
| **英文优先** | 所有填写内容用英文，中文材料附上英文翻译 |
| **不要用 VPN 注册** | 用香港或海外 IP 注册，大陆 IP 可能触发风控 |
| **审核期间不要改信息** | 提交后等结果，频繁修改会延长审核 |

### 4.2 合规相关

| 注意点 | 说明 |
|--------|------|
| **服务条款 + 退款政策** | Stripe 强制要求网站上有这两个页面，没有会暂停账户 |
| **隐私政策** | GDPR/CCPA 要求，收集用户数据必须有隐私政策页面 |
| **公司域名邮箱** | 联系方式用 `xxx@genz.ltd`，不要用个人邮箱 |
| **定价透明** | 网站上的价格必须跟 Stripe 产品价格一致 |
| **不要收敏感行业费用** | 赌博、成人内容、加密货币等 Stripe 禁止的行业不要碰 |

### 4.3 资金相关

| 注意点 | 说明 |
|--------|------|
| **结算周期** | Stripe 香港默认 T+7（首笔），后续可缩短到 T+2 |
| **提现费用** | Stripe → 香港银行账户，HKD 免费提现，USD 有 0.5% 汇率费 |
| **交易手续费** | 香港地区 3.4% + HK$2.35/笔（国际卡） |
| **退款** | 退款不退手续费，只退本金 |
| **争议费用** | 每笔争议（Chargeback）扣 HK$80 |
| **首次冻结** | 新账户首笔交易可能冻结 7-14 天，后续正常 |

### 4.4 税务相关

| 注意点 | 说明 |
|--------|------|
| **香港利得税** | 香港公司利润 200 万港币以内 8.25%，超过 16.5% |
| **不做香港本地生意可申请离岸豁免** | 如果客户全在海外，可向税局申请离岸豁免，税率 0% |
| **不需要收 GST/VAT** | 香港没有销售税/VAT，不用给客户加税费 |
| **海外客户 VAT** | 欧盟/英国/澳洲客户超过阈值需注册当地 VAT，Stripe Tax 可自动处理 |
| **做账审计** | 香港公司每年需要做账 + 审计，找会计师处理（费用约 HK$5,000-10,000/年） |

---

## 五、时间线估算

| 步骤 | 预计时间 | 备注 |
|------|----------|------|
| 确认前置材料齐全 | 1-2 天 | 如果 BR 过期需先续期 |
| 网站准备（landing + legal pages） | 1-2 天 | 可以用模板快速搭 |
| Stripe 注册填写 | 30 分钟 | 在线填写 |
| Stripe 审核 | 1-3 个工作日 | 首次可能更长 |
| 创建产品 + Webhook | 30 分钟 | 审核通过后 |
| VPS 配置 + 测试 | 1 小时 | 改 .env + 重启 + 测试支付 |
| **总计** | **约 1 周** | 材料齐全的情况下 |

---

## 六、清单总览（打印对照用）

### 注册前
- [ ] CR（公司注册证书）
- [ ] BR（商业登记证，在有效期内）
- [ ] 香港公司银行账户（能收 USD）
- [ ] 银行月结单（3 个月内）
- [ ] 董事护照或香港身份证
- [ ] 董事住址证明（3 个月内）
- [ ] genz.ltd 首页上线（有产品介绍 + 定价）
- [ ] /terms 服务条款页面
- [ ] /refund 退款政策页面
- [ ] /privacy 隐私政策页面
- [ ] 公司域名邮箱（zervi@genz.ltd）

### 注册中
- [ ] 选 Hong Kong
- [ ] 选 Company/Business 类型
- [ ] 公司英文名跟 CR 一致
- [ ] 填公司编号
- [ ] 业务描述（英文）
- [ ] 产品 URL 填 genz.ltd
- [ ] 绑定银行账户 + 上传月结单
- [ ] 填负责人信息 + 上传证件
- [ ] 提交

### 注册后
- [ ] 拿到 pk_ / sk_ keys
- [ ] 创建 Stripe Products + Prices
- [ ] 拿到 price_ IDs
- [ ] 配置 Webhook endpoint
- [ ] 拿到 whsec_ secret
- [ ] VPS .env 配置 5 个 Stripe 参数
- [ ] 重启 backend 容器
- [ ] 测试卡跑通支付流程
- [ ] 验证 Webhook 回调
- [ ] 验证数据库订单写入
