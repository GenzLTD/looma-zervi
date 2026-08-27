import type { PaymentRegion } from "@looma/shared-core";

/** CN = 大陆腾讯云；SG = 海外 Vultr 新加坡 */
export const DEPLOY_REGION = (import.meta.env.VITE_DEPLOY_REGION || "CN") as "CN" | "SG";

export const IS_OVERSEAS = DEPLOY_REGION === "SG";

export const BILLING_REGION: PaymentRegion = IS_OVERSEAS ? "US" : "CN";
