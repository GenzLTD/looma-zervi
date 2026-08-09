/**
 * P1 — Candidates overseas closed-loop (API only).
 *
 * Browser UI lives in candidates-overseas.live.spec.ts (overseas.live.config).
 * This file is safe under playwright.overseas.api.config.ts (no SaaS webServer).
 *
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:candidates:api
 */
import { test, expect } from "@playwright/test";
import {
  seedOverseasSeekerWithShareCode,
  registerOverseasUser,
  createEnterprise,
  importCandidateFromShare,
  listEnterpriseCandidates,
  getEnterpriseCandidate,
  getPublicProfileView,
  tryUpgradeToken,
} from "./helpers/overseasApi";

test.describe("candidates overseas API @overseas @live @api", () => {
  test.describe.configure({ mode: "serial" });

  let shareCode: string;
  let personalityName: string;
  let seekerDisplayName: string;
  let supporterToken: string | null = null;

  test.beforeAll(async () => {
    const seeded = await seedOverseasSeekerWithShareCode();
    shareCode = seeded.shareCode;
    personalityName = seeded.personalityName;
    seekerDisplayName = seeded.displayName;
  });

  test("public profile-view returns seeded personality", async () => {
    const view = await getPublicProfileView(shareCode);
    expect(view.personality_type || view).toBeTruthy();
    const detailRaw = String(view.personality_detail || "");
    expect(
      detailRaw.includes(personalityName) || view.personality_type === personalityName,
    ).toBe(true);
  });

  test("free HR can create enterprise but import is tier-gated", async () => {
    const hr = await registerOverseasUser("E2E HR Overseas");

    const enterprise = await createEnterprise(hr.token, `Overseas E2E ${Date.now()}`);
    expect(enterprise.id).toBeTruthy();

    const denied = await importCandidateFromShare(hr.token, shareCode);
    expect(denied.status).toBe(403);
    expect(String(denied.body.error)).toMatch(/forbidden/i);
    expect(String(denied.body.message)).toMatch(/supporter/i);

    const upgrade = await tryUpgradeToken(hr.token, "supporter");
    if (upgrade.ok) {
      supporterToken = upgrade.token;
    } else {
      expect(upgrade.status).toBe(402);
      test.info().annotations.push({
        type: "note",
        description:
          "PAYMENT_STUB_MODE off — full import needs local stub or real Stripe/supporter seed.",
      });
    }
  });

  test("import + list + detail when supporter available", async () => {
    test.skip(!supporterToken, "supporter upgrade unavailable on this environment");

    const imported = await importCandidateFromShare(supporterToken!, shareCode);
    expect([200, 201]).toContain(imported.status);
    expect(imported.body.id || imported.body.candidate).toBeTruthy();

    const list = await listEnterpriseCandidates(supporterToken!);
    expect(list.status).toBe(200);
    const candidates = (list.body.candidates as Array<Record<string, unknown>>) || [];
    expect(candidates.length).toBeGreaterThan(0);

    const candidateId = String(candidates[0].id);
    const detail = await getEnterpriseCandidate(supporterToken!, candidateId);
    expect(detail.status).toBe(200);
    expect(
      String(detail.body.name || detail.body.user_display || "").includes(seekerDisplayName) ||
        String(detail.body.personality_type || "").includes(personalityName),
    ).toBe(true);
  });
});
