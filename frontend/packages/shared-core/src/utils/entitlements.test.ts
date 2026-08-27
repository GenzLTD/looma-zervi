import { describe, expect, it } from "vitest";
import { hasMinTier, isAdmin, isPaidTier } from "./entitlements";

describe("entitlements", () => {
  it("hasMinTier respects TIER_ORDER", () => {
    expect(hasMinTier("free", "supporter")).toBe(false);
    expect(hasMinTier("supporter", "supporter")).toBe(true);
    expect(hasMinTier("pro", "supporter")).toBe(true);
    expect(hasMinTier("enterprise", "pro")).toBe(true);
    expect(hasMinTier("guest", "free")).toBe(false);
    expect(hasMinTier(null, "free")).toBe(false);
    expect(hasMinTier("unknown", "free")).toBe(false);
  });

  it("isPaidTier treats supporter+", () => {
    expect(isPaidTier("free")).toBe(false);
    expect(isPaidTier("supporter")).toBe(true);
    expect(isPaidTier("pro")).toBe(true);
  });

  it("isAdmin only matches admin role", () => {
    expect(isAdmin("admin")).toBe(true);
    expect(isAdmin("user")).toBe(false);
    expect(isAdmin(null)).toBe(false);
  });
});
