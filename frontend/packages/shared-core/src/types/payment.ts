/**
 * Payment types — 与 backend/contracts/payment.v1.json 对齐
 * Ownership: JOINT (dual-review required)
 */

import type { Tier } from "./auth";

/** 区域码（与 payment.v1.json regions 一致） */
export type PaymentRegion = "CN" | "US";

/** 支付方式 */
export type PaymentTradeType = "NATIVE" | "JSAPI";

/** 支付服务商（海外） */
export type PaymentProvider = "wechat" | "stripe" | "paypal" | "airwallex";

/** 定价计划（GET /v1/payment/plans 单条） */
export interface PaymentPlan {
  tier: Tier;
  name: string;
  price_monthly: number;
  currency: string;
  region: PaymentRegion;
  plan_id: string;
  features: string[];
  upgradable?: boolean;
}

/** GET /v1/payment/plans 响应 */
export interface PlansResponse {
  region: PaymentRegion;
  currency: string;
  payment_provider: PaymentProvider;
  payment_providers?: PaymentProvider[];  // Multi-provider regions (overseas)
  plans: PaymentPlan[];
  stub_mode?: boolean;
}

/** GET /v1/payment/status 响应 */
export interface PaymentStatus {
  tier: Tier;
  plan: PaymentPlan;
  status: "active" | "expired" | "cancelled" | "inactive";
  expires_at: string | null;
  stub_mode?: boolean;
  /** 支付成功后后端可能返回新 token（tier 变更后需刷新会话） */
  access_token?: string;
}

/** POST /v1/payment/upgrade 请求 */
export interface UpgradeRequest {
  tier: "supporter" | "pro";
  region?: PaymentRegion;
}

/** POST /v1/payment/upgrade 响应 */
export interface UpgradeResponse {
  tier: Tier;
  plan: PaymentPlan;
  status: string;
  message: string;
  access_token?: string;
  token_type?: "bearer";
  expires_in?: number;
}

/** POST /v1/payment/wechat/order 请求 */
export interface WechatOrderRequest {
  tier: "supporter" | "pro";
  trade_type?: PaymentTradeType;
  openid?: string;
}

/** POST /v1/payment/wechat/order 响应 — JSAPI 参数 */
export interface WechatJsapiParams {
  appId: string;
  timeStamp: string;
  nonceStr: string;
  package: string;
  signType: "RSA";
  paySign: string;
}

/** POST /v1/payment/wechat/order 响应 */
export interface WechatOrderResponse {
  order_id: string;
  out_trade_no: string;
  prepay_id: string;
  qr_code_url: string;
  amount: number;
  currency: string;
  tier: Tier;
  jsapi_params?: WechatJsapiParams;
}

/** 契约内 supporter 区域定价（文档/测试对照用） */
export const PAYMENT_SUPPORTER_PRICES = {
  CN: { amount: 9.9, currency: "CNY" as const },
  US: { amount: 1.99, currency: "USD" as const },
} as const;

/** 契约内 pro 区域定价 */
export const PAYMENT_PRO_PRICES = {
  CN: { amount: 29.9, currency: "CNY" as const },
  US: { amount: 5.99, currency: "USD" as const },
} as const;

/** @deprecated 旧 Tatha basic → supporter */
export const DEPRECATED_TIER_ALIASES = {
  basic: "supporter",
} as const;

/** POST /v1/payment/checkout 请求 */
export interface CheckoutRequest {
  provider: PaymentProvider;
  tier: "supporter" | "pro";
  mode?: "payment" | "subscription";
  success_url?: string;
  cancel_url?: string;
  /**
   * 账单区。仅用于报价展示（``/v1/payment/plans``）与海外 CN 闸的判定参数。
   *
   * 它**不再决定下单金额**。金额与币种由所选支付通道决定：卡通道（stripe /
   * paypal / airwallex）恒按 USD 套餐计价，钱包通道恒按 CNY 套餐计价 —— 后端
   * ``billing_region_for_provider()`` 从 contracts/payment.v1.json 反查这条归属，
   * amount 与 currency 都取自同一份 plan。
   *
   * 历史 bug：三者曾被分别读取（plan 金额 + config 币种 + 常量表给通道），
   * 于是一笔 $1.99 的卡支付被记成「9.9 USD」。
   */
  region?: PaymentRegion;
}

/** POST /v1/payment/checkout 响应 */
export interface CheckoutResponse {
  order_id: string;
  out_trade_no: string;
  provider: PaymentProvider;
  checkout_url: string;
  amount: number;
  currency: string;
  tier: "supporter" | "pro";
}

/** GET /v1/payment/providers 响应 */
export interface ProvidersResponse {
  region: PaymentRegion;
  providers: PaymentProvider[];
  stub_mode: boolean;
}

/**
 * ============ Apple IAP（payment.v1.json v1.2.0 apple_iap 段）============
 *
 * App 内 StoreKit 2 通道，服务端为 zervi-rust payment-service（:3009）。
 * 与 huawei_iap 同理**不属于** `PaymentProvider` union —— 那是 web checkout
 * 通道（stripe/paypal/...），Apple IAP 不出现在 web 结账页。
 * 服务端实现：zervi-rust feat/apple-iap 分支 payment-service/src/routes.rs。
 */

/** POST /v1/payment/apple/verify 请求（App 内购买完成后主动查证，激活主路径） */
export interface AppleVerifyRequest {
  /** StoreKit 2 交易返回的 transaction.id（每次续期不同） */
  transactionId: string;
}

/** POST /v1/payment/apple/restore 请求（跨设备恢复，重新绑定当前账号） */
export interface AppleRestoreRequest {
  originalTransactionId: string;
}

/** POST /v1/payment/apple/verify | restore 响应 */
export interface AppleIapStatus {
  tier: Tier;
  /** 订阅当前是否有效（expiresDate 在未来） */
  active: boolean;
  /** RFC3339 */
  expiresAt: string;
  environment: "Sandbox" | "Production";
  originalTransactionId: string;
}
