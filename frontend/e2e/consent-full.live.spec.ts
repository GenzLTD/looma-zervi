/**
 * P1 — Full consent scope grant → verify → revoke (overseas API)
 *
 * Covers primary tiers + other product scopes used by overseas SaaS.
 * Legacy children (resume_parse, etc.) are covered via jobseeker_core package expand.
 *
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:consent
 */
import { test, expect } from "@playwright/test";
import {
  registerOverseasUser,
  grantConsent,
  revokeConsent,
  getConsentStatus,
  getRequiredConsents,
  OVERSEAS_CONSENT_SCOPES,
} from "./helpers/overseasApi";

test.describe.configure({ mode: "serial" });

test.describe("consent full scopes @overseas @live", () => {
  test("required endpoint lists primary tiers + available scopes", async () => {
    const required = await getRequiredConsents();
    expect(required.primary_tiers).toEqual(
      expect.arrayContaining(["jobseeker_core", "credit_query", "report_share"]),
    );
    for (const scope of OVERSEAS_CONSENT_SCOPES) {
      expect(required.available_scopes).toContain(scope);
    }
  });

  test("grant → status true → revoke → status false for each overseas scope", async () => {
    const { token } = await registerOverseasUser("E2E Consent Full");

    const before = await getConsentStatus(token);
    for (const scope of OVERSEAS_CONSENT_SCOPES) {
      expect(before.status[scope]).toBeFalsy();
    }

    for (const scope of OVERSEAS_CONSENT_SCOPES) {
      await grantConsent(token, scope);
      const granted = await getConsentStatus(token);
      expect(granted.status[scope]).toBe(true);

      // Package scopes expand children
      if (scope === "jobseeker_core") {
        expect(granted.status.resume_parse).toBe(true);
        expect(granted.status.job_match).toBe(true);
      }
      if (scope === "credit_query") {
        expect(granted.status.credit_analyze).toBe(true);
      }

      const revoked = await revokeConsent(token, scope);
      expect(revoked.revoked).toBe(true);

      const after = await getConsentStatus(token);
      expect(after.status[scope]).toBeFalsy();
    }
  });

  test("re-grant after revoke works", async () => {
    const { token } = await registerOverseasUser("E2E Consent Regrant");
    await grantConsent(token, "ask_rag");
    await revokeConsent(token, "ask_rag");
    await grantConsent(token, "ask_rag");
    const status = await getConsentStatus(token);
    expect(status.status.ask_rag).toBe(true);
  });
});
