/**
 * Compliance Gate E2E — consent required before credit check
 */
import { test, expect } from "@playwright/test";
import {
  registerAndGetToken,
  grantConsent,
  checkCompanyCredit,
  uniqueHrEmail,
  API_BASE,
} from "./helpers/liveApi";

test.describe("compliance consent @live", () => {
  test("credit check returns 403 without consent, succeeds after grant", async () => {
    const token = await registerAndGetToken(uniqueHrEmail());

    const denied = await checkCompanyCredit(token, "测试科技有限公司");
    expect(denied.status).toBe(403);
    expect(denied.body.error).toBe("consent_required");
    expect(denied.body.required_scope).toBe("credit_query");

    await grantConsent(token, "credit_query");

    const allowed = await checkCompanyCredit(token, "测试科技有限公司");
    expect(allowed.status).toBe(200);
    expect(allowed.body.extracted).toBeTruthy();
    expect(allowed.body.warning).toContain("AI 训练知识评估");
  });

  test("consent status reflects granted scope", async () => {
    const token = await registerAndGetToken(uniqueHrEmail("consent-status"));

    const before = await fetch(`${API_BASE}/v1/compliance/consent/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(before.ok).toBe(true);
    const beforeJson = (await before.json()) as { status: Record<string, boolean> };
    expect(beforeJson.status.credit_query).toBe(false);

    await grantConsent(token, "credit_query");

    const after = await fetch(`${API_BASE}/v1/compliance/consent/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const afterJson = (await after.json()) as { status: Record<string, boolean> };
    expect(afterJson.status.credit_query).toBe(true);
  });
});
