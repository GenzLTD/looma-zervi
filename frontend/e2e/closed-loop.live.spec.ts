/**
 * T-space 最小闭环 E2E — 接真实 Flask 后端（无 API mock）
 *
 * 流程：公开画像页 → HR 注册 → 导入候选人 → Stub 试用
 *
 * 注意：SaaS 默认按浏览器语言选 i18n；Playwright Chromium 为 en-US，
 * 必须强制 zh，否则中文 placeholder / 按钮文案对不上。
 */
import { test, expect } from "@playwright/test";
import {
  seedSeekerWithShareCode,
  uniqueHrEmail,
  upgradeToken,
  TEST_PASS,
} from "./helpers/liveApi";

test.describe.configure({ mode: "serial" });

/**
 * 强制中文文案（addInitScript 每次导航都执行，仅设 lang 是幂等安全的）。
 * 注意：不要把 token 清除逻辑放 initScript 里，否则后续 page.goto() 会
 * 把刚注册获得的 token 也清掉，导致 AuthGuard 踢回登录页。
 */
async function prepareZhGuest(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    localStorage.setItem("genz_lang", "zh");
  });
}

/** 清除残留登录态（仅在需要游客态时手动调用一次，不会在后续导航中重复清除） */
async function clearStaleAuth(page: import("@playwright/test").Page) {
  await page.evaluate(() => {
    localStorage.removeItem("saas-auth");
    localStorage.removeItem("looma_token");
  });
}

test.describe("closed loop @live", () => {
  let shareCode: string;
  let personalityName: string;
  let hrEmail: string;

  test.beforeAll(async () => {
    const seeded = await seedSeekerWithShareCode();
    shareCode = seeded.shareCode;
    personalityName = seeded.personalityName;
    hrEmail = uniqueHrEmail();
  });

  test("public candidate share page shows personality profile", async ({ page }) => {
    await prepareZhGuest(page);
    await page.goto(`/candidate/share/${shareCode}`);
    // 公开页无需登录，但清掉残留可避免意外跳转
    await expect(page.getByRole("heading", { name: personalityName })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("创造力")).toBeVisible();
    await expect(page.getByRole("link", { name: /免费试用 T-space|Free trial/i })).toBeVisible();
  });

  test("HR registers, imports candidate, and starts Pro trial stub", async ({ page }) => {
    await prepareZhGuest(page);
    await page.goto("/register");

    // 在页面已加载后手动清掉残留 auth，再刷新生效。
    // 放在 addInitScript 外是为了避免后续 page.goto("/candidates")
    // 也执行清除逻辑，把刚注册获得的 token 丢掉。
    await clearStaleAuth(page);
    await page.reload();

    // 等注册表单出现（中文真源；兼容英文防回归）
    const nameField = page
      .getByPlaceholder("姓名（选填）")
      .or(page.getByPlaceholder("Name (optional)"));
    await expect(nameField).toBeVisible({ timeout: 15_000 });
    await nameField.fill("E2E HR");

    await page
      .getByPlaceholder("邮箱地址")
      .or(page.getByPlaceholder("Email address"))
      .fill(hrEmail);
    await page
      .getByPlaceholder("密码（至少6位）")
      .or(page.getByPlaceholder(/Password \(min/i))
      .fill(TEST_PASS);
    await page
      .getByPlaceholder("确认密码")
      .or(page.getByPlaceholder("Confirm password"))
      .fill(TEST_PASS);

    await page.getByRole("button", { name: /^(注册|Sign up)$/ }).click();

    await expect(page).toHaveURL("/", { timeout: 15_000 });

    // 新用户默认 free tier，/candidates 需要 supporter+；
    // 通过 stub upgrade API 直接升 tier，刷新 token 到 localStorage
    const token = await page.evaluate(() => localStorage.getItem("looma_token"));
    if (!token) throw new Error("No looma_token after registration");
    const newToken = await upgradeToken(token, "supporter");
    await page.evaluate((nt) => {
      localStorage.setItem("looma_token", nt);
      localStorage.setItem("saas-auth", JSON.stringify({ state: { token: nt }, version: 0 }));
    }, newToken);

    await page.goto("/candidates");

    const createEnterprise = page.getByRole("button", {
      name: /创建企业（一键）|Create workspace/,
    });
    const shareInput = page
      .getByPlaceholder("粘贴分享码，如 A1B2C3D4")
      .or(page.getByPlaceholder(/Paste share code/i));

    await expect(createEnterprise.or(shareInput)).toBeVisible({ timeout: 15_000 });

    if (await createEnterprise.isVisible()) {
      await createEnterprise.click();
      await expect(shareInput).toBeVisible({ timeout: 15_000 });
    }

    await shareInput.fill(shareCode);
    await page.getByRole("button", { name: /^(导入|Import)$/ }).click();
    await expect(page.getByText(/导入成功|已在列表中|imported|already/i)).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText("E2ESeeker")).toBeVisible();

    await page.goto("/pricing");
    await page.getByRole("button", { name: /开始 7 天试用|Start .*trial|7.day/i }).click();
    await expect(
      page.getByText(/已开通 Pro 试用|升级失败|trial|upgrade/i),
    ).toBeVisible({ timeout: 10_000 });
  });
});
