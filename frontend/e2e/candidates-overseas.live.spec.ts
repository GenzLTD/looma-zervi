/**
 * P1 — Candidates overseas closed-loop (browser / SaaS UI).
 *
 * API-only coverage: candidates-overseas.api.live.spec.ts
 *
 * Requires SaaS (local :5174 or production). Use overseas.live.config.ts:
 *
 *   E2E_OVERSEAS_WEB=https://genz.ltd \
 *   E2E_OVERSEAS_SAAS=https://tspace.genz.ltd \
 *   E2E_OVERSEAS_API=https://api.genz.ltd \
 *   pnpm e2e:overseas:candidates
 */
import { test, expect } from "@playwright/test";
import {
  seedOverseasSeekerWithShareCode,
  registerOverseasUser,
  createEnterprise,
  tryUpgradeToken,
  TEST_PASS,
  OVERSEAS_SAAS_BASE,
} from "./helpers/overseasApi";

async function prepareEnGuest(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    localStorage.setItem("genz_lang", "en");
  });
}

async function clearStaleAuth(page: import("@playwright/test").Page) {
  await page.evaluate(() => {
    localStorage.removeItem("saas-auth");
    localStorage.removeItem("looma_token");
  });
}

async function injectSaasAuth(page: import("@playwright/test").Page, token: string) {
  await page.evaluate((t) => {
    localStorage.setItem(
      "saas-auth",
      JSON.stringify({ state: { token: t }, version: 0 }),
    );
    localStorage.setItem("looma_token", t);
  }, token);
}

test.describe("candidates overseas browser @overseas @live", () => {
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

  test("public share page shows personality", async ({ page }) => {
    await prepareEnGuest(page);
    await page.goto(`${OVERSEAS_SAAS_BASE}/candidate/share/${shareCode}`);
    await expect(page.getByRole("heading", { name: personalityName })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText("Creativity")).toBeVisible();
    // Share page CTA is still ZH hard-coded in CandidateShare.tsx today
    await expect(
      page.getByRole("link", { name: /免费试用 T-space|Free trial/i }),
    ).toBeVisible();
  });

  test("HR imports candidate on /candidates when supporter available", async ({ page }) => {
    if (!supporterToken) {
      const hr = await registerOverseasUser("E2E HR Browser");
      await createEnterprise(hr.token, `Overseas Browser ${Date.now()}`);
      const upgrade = await tryUpgradeToken(hr.token, "supporter");
      if (upgrade.ok) {
        supporterToken = upgrade.token;
      }
    }
    test.skip(!supporterToken, "supporter upgrade unavailable on this environment");

    await prepareEnGuest(page);
    await page.goto(`${OVERSEAS_SAAS_BASE}/register`);
    await clearStaleAuth(page);
    await injectSaasAuth(page, supporterToken!);
    await page.goto(`${OVERSEAS_SAAS_BASE}/candidates`);

    const createEnterpriseBtn = page.getByRole("button", {
      name: /Create workspace|创建企业/,
    });
    const shareInput = page
      .getByPlaceholder(/Paste (candidate )?share code/i)
      .or(page.getByPlaceholder(/粘贴(候选人)?分享码/));

    await expect(createEnterpriseBtn.or(shareInput)).toBeVisible({ timeout: 20_000 });

    if (await createEnterpriseBtn.isVisible()) {
      await createEnterpriseBtn.click();
      await expect(shareInput).toBeVisible({ timeout: 15_000 });
    }

    await shareInput.fill(shareCode);
    await page.getByRole("button", { name: /^(Import|导入)$/ }).click();
    await expect(
      page.getByText(/Candidate imported|already|导入成功|已在列表中|imported/i),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(seekerDisplayName)).toBeVisible();

    // Prod may still be card UI (name link); local Untitled table has "View"
    const viewLink = page.getByRole("link", { name: /^(View|查看)$/ });
    const nameLink = page.getByRole("link", { name: seekerDisplayName });
    if (await viewLink.count()) {
      await viewLink.first().click();
    } else {
      await nameLink.first().click();
    }
    await expect(page).toHaveURL(/\/candidates\//, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: seekerDisplayName }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(new RegExp(personalityName))).toBeVisible();
  });

  test("HR register page is English on overseas SaaS", async ({ page }) => {
    await prepareEnGuest(page);
    await page.goto(`${OVERSEAS_SAAS_BASE}/register`);
    await clearStaleAuth(page);
    await page.reload();

    await expect(page.getByPlaceholder(/email/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByPlaceholder(/password/i).first()).toBeVisible();
    const body = await page.textContent("body");
    expect(body).not.toMatch(/邮箱地址|确认密码/);

    const email = `e2e-hr-ui-${Date.now()}@test.local`;
    await page
      .getByPlaceholder(/Name \(optional\)|姓名/)
      .fill("E2E HR UI");
    await page.getByPlaceholder(/email/i).fill(email);
    await page.getByPlaceholder(/password/i).first().fill(TEST_PASS);
    const confirm = page.getByPlaceholder(/Confirm password|确认密码/i);
    if (await confirm.isVisible()) {
      await confirm.fill(TEST_PASS);
    }
    await page.getByRole("button", { name: /sign up|register/i }).click();
    await expect(page).toHaveURL(/\/($|\?)/, { timeout: 20_000 });
  });
});
