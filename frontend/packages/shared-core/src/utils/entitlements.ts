/**
 * Tier / role entitlement helpers.
 * Aligned with backend `require_tier` / `_require_admin` and `TIER_ORDER`.
 */
import { TIER_ORDER } from "../constants/quota";
import type { Role, Tier } from "../types/auth";

export type TierLike = Tier | "guest" | string;

/** True when userTier is at least `min` (free < supporter < pro < enterprise). */
export function hasMinTier(
  userTier: TierLike | null | undefined,
  min: Tier,
): boolean {
  if (!userTier) return false;
  const userRank = TIER_ORDER[userTier as keyof typeof TIER_ORDER];
  const minRank = TIER_ORDER[min];
  if (userRank === undefined || minRank === undefined) return false;
  return userRank >= minRank;
}

/** Paid tiers: supporter / pro / enterprise. */
export function isPaidTier(tier?: TierLike | null): boolean {
  return hasMinTier(tier, "supporter");
}

export function isAdmin(role?: Role | string | null): boolean {
  return role === "admin";
}
