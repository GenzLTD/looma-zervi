# YeDall ↔ looma-zervi · 边界与实体分轨（草案）

> **版本：** 0.1-draft · **日期：** 2026-07-20  
> **状态：** 草案 — 供团队对齐；**不触发任何线上部署**  
> **规范副本：** 与桌面仓 `YeDall/BOUNDARY.md` 同步；冲突时以团队决议更新两边  
> **前提：** 海外实体许可 / 商户审核完成前，不跑通应用层变现闭环；协议与工程可并行准备  
> **关联：** [MANIFESTO.md](./MANIFESTO.md) · [DUAL_TRACK_ACCEPTANCE_CHECKLIST.md](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md) · [COMMERCE_ENTITY_DECISION.md](./COMMERCE_ENTITY_DECISION.md)

---

## 0. 一句话

> **协议与海外变现主体在 YeDall（YEDALL LIMITED）；大陆变现主体在 szbolent；场景与工程实现在 looma-zervi。**  
> YeDall「不独占」的是招聘/匹配产品本身，**不是**海外支付。

---

## 1. 三方角色

| 角色 | 是什么 | 拥有什么 | 不拥有什么 |
|------|--------|----------|------------|
| **YEDALL LIMITED** | 香港法律实体 / 海外品牌伞 | 海外签约、开票、商户责任；USD 收款路径（Stripe / PayPal / Airwallex）；`genz.ltd` 审核可见的法律与支付叙事 | 大陆微信商户；国内 ICP / 小程序主体 |
| **szbolent（大陆实体）** | 大陆法律实体 | 备案域、微信登录/支付商户、CNY 变现路径（规划 / 进行中：`szbolent.com.cn` 等） | 海外 Stripe 商户面 |
| **looma-zervi** | 工程与产品应用仓 | PlanetX / T-space / 双端部署 / 支付**实现**与 webhook / 记忆生产 / 配额与 tier | 法律主体身份；对外商户合同的甲方名义 |

**YeDall 代码仓**定位为：**信任协议真源 + 海外主体叙事的工程锚点**（契约、验证参考实现、协议 CLI/MCP），不是第二套招聘 SaaS。

---

## 2. 实体分轨 · 变现覆盖面

目标：用**两个主体**补齐变现路径，用**一套 looma 支付内核**做技术实现。

```
                    ┌─────────────────────────┐
                    │   looma-zervi 支付引擎   │
                    │  plans / checkout /     │
                    │  webhook / tier 升级    │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
              ▼                                   ▼
   region=US / OVERSEAS                  region=CN / 大陆
   商户与合同：YEDALL LIMITED            商户与合同：szbolent
   渠道：Stripe / PayPal / Airwallex     渠道：微信支付等
   获客壳：genz.ltd（审核期冻结乱改）      获客/端：小程序 / 门户等
```

| 维度 | 海外轨 | 大陆轨 |
|------|--------|--------|
| 法律主体 | **YEDALL LIMITED** | **szbolent** |
| 货币 | USD | CNY |
| 支付通道 | Stripe 等（YeDall 商户） | 微信等（szbolent 商户） |
| 产品壳 | genz.ltd / tspace（工程在 looma） | PlanetX / 小程序 / 规划域名 |
| 验收真源 | OS-P0/P1（双线清单） | CN-P0/P1 |

**结论（对前一版口头草案的修正）：**

- ❌ 旧表述：「YeDall 不拥有支付」  
- ✅ 新表述：**YEDALL LIMITED 拥有海外支付的商业与合规所有权**；looma **实现并运维**支付能力，并按 `region` / 部署轨把结算归到对应实体。

---

## 3. 协议层 vs 应用层

| 层 | 真源 | 内容 |
|----|------|------|
| **协议层** | **YeDall 仓优先** | 信任如何被声明、授权、验证、审计；attestation / verify / MCP；share_code 语义；对外摘要（**不做**用户可见信任分） |
| **应用层** | **looma-zervi** | 行为记忆如何被生产；PlanetX / T-space；简历匹配、配额、游戏化；信任档案 UI（产品出口） |
| **交接面** | 契约 + API | looma 写 memories / 触发签发；第三方与 CLI/MCP 走验证面（YeDall 规范，短期可仍由 looma 托管运行） |

### 3.1 looma-zervi 继续拥有的

- 场景产品与记忆生产  
- 支付代码、CORS、部署、海外 tag 发版（Vultr 等）  
- 现网 trust 运行面（Ed25519 / share_code / audit / `looma-cli`）— **过渡期实现**，契约应对齐 YeDall  

### 3.2 应用层不做的（本阶段）

- **实体许可审核完成前**：不把「海外/双轨变现已跑通」写成验收结论  
- 审核期不改 `genz.ltd` 审核敏感面  

---

## 4. 当前冻结与解锁条件

### 4.1 现在冻结（不动线上）

| 冻结项 | 原因 |
|--------|------|
| **Vercel / `genz.ltd` 营销与法律页乱改** | 海外实体 / Stripe 等许可审核进行中 |
| **宣称「应用层海外变现已跑通」** | 主体许可未落地前，商业闭环不完整 |
| **以发版压力驱动协议仓大重构** | 先边界清晰，再拆进程 |

允许并行：YeDall 契约与协议测试；looma 仓内工程改进（不部署审核敏感面）；Vultr 内部能力维护。

### 4.2 解锁之后再做（已定调）

> **等实体许可审核下来，再跑通应用层业务模型。**

解锁后优先序建议：

1. 确认 YEDALL 商户与 webhook / Checkout 实单归 YeDall  
2. 修正获客 CTA 等产品一致性（审核通过后再动 Vercel）  
3. 应用层：订阅 → tier → 配额 → 核心场景变现闭环验收  
4. 协议层：YeDall ↔ looma trust 字段对照表落地，必要时再拆验证进程  

---

## 5. 过渡期信任实现策略

| 阶段 | 做法 |
|------|------|
| **现在** | looma 现网 trust + `looma-cli` 作 server–terminal 演示；YeDall 契约 **normative**，looma `trust.v1` **transitional** |
| **许可后** | 应用层变现按实体分轨验收；协议字段收敛到 YeDall |
| **远期** | Trust Agent 可近记忆（looma），**输出 schema 与 verify API 服从 YeDall** |

**禁止：** 两套长期不兼容的 attestation / share_code 语义并行对外。

---

## 6. 决策记录

1. **YEDALL LIMITED 拥有海外支付商业与合规所有权**（纠正「YeDall 不拥有支付」）。  
2. 大陆变现由 **szbolent** 覆盖，与 YeDall 分轨互补。  
3. looma-zervi 是实现仓，不是收款甲方。  
4. **线上部署与应用层变现验收延后至实体许可审核完成**。  

---

## 7. 修订

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1-draft | 2026-07-20 | 首版：实体分轨 + 协议/应用边界 + 审核期冻结 |
