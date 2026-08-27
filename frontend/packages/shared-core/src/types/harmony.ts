/**
 * HarmonyOS cloud kit contracts (Auth / IAP / Push / Card).
 * Mirror backend camelCase bodies — see contracts/harmony.v1.json.
 */

import type { AuthResponse } from "./auth";

/** POST /v1/auth/huawei */
export interface HuaweiAuthRequest {
  authorizationCode: string;
  state?: string;
}

export interface HuaweiAuthResponse extends AuthResponse {
  user: AuthResponse["user"] & { is_new_user?: boolean };
}

/** POST /v1/payment/huawei/notify */
export interface HuaweiIapNotifyRequest {
  purchaseData: string;
  purchaseSignature: string;
  signatureAlgorithm?: string;
  expectedProductId?: string;
  expectedAmount?: string;
}

export interface HuaweiIapNotifyResponse {
  result: "OK" | "FAIL";
  message: string;
  order_id?: string;
}

/** POST /v1/payment/huawei/verify (stub 501) */
export interface HuaweiIapVerifyRequest {
  purchaseToken: string;
  productId: string;
}

export interface HuaweiIapVerifyResponse {
  verified: boolean;
  message: string;
  hint?: string;
}

/** POST /v1/push/huawei/register | unregister */
export interface HuaweiPushTokenRequest {
  pushToken: string;
}

export interface HuaweiPushRegisterResponse {
  status: "registered" | "unregistered";
  user_id?: string;
}

/** POST /v1/push/huawei/send */
export interface HuaweiPushSendRequest {
  title?: string;
  body: string;
  category?: "MARKETING" | "SOCIAL" | "SERVICE" | string;
  clickData?: Record<string, unknown>;
  testMode?: boolean;
}

export interface HuaweiPushSendResponse {
  success?: boolean;
  status?: string;
  message?: string;
  error?: string;
  data?: Record<string, unknown>;
}

export type HarmonyCardType = "weather" | "profile" | "status" | "activity";

export interface HarmonyCardItem {
  cardId: string;
  type: HarmonyCardType | string;
  data: Record<string, unknown>;
  ttl: number;
  timestamp: number;
}

export interface HarmonyCardBatchRequest {
  cards: Array<{ cardId: string; type?: HarmonyCardType | string }>;
}
