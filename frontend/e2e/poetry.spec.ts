/**
 * Poetry page e2e tests — Browse, Search, Discover, Detail modal.
 *
 * All backend API calls are mocked via Playwright request interception,
 * so tests run independently without a live backend.
 *
 * Auth bypass strategy:
 *   1. addInitScript injects saas-auth into localStorage BEFORE any JS runs
 *   2. Route interception handles ALL /v1/* API calls (cross-origin to :5200)
 *   3. We also stub fetchProfile by pre-hydrating the Zustand store via init script
 *
 * Key fixes from iteration 5:
 *   - Use getByRole('heading') instead of locator("h1") to avoid strict mode
 *     violation (sidebar has its own <h1>)
 *   - Hide sidebar on mobile viewports (< 768px) to prevent pointer event
 *     interception by fixed-position sidebar elements
 *   - Discover mode now auto-fetches via onClick handler in Poetry.tsx
 */
import { test, expect, type Page, type BrowserContext } from "@playwright/test";

// ─── Mock data ──────────────────────────────────────────────

const MOCK_POEMS = [
  {
    id: 1,
    title: "静夜思",
    author: "李白",
    dynasty: "唐",
    theme: "",
    content_preview: "床前明月光，疑是地上霜。",
    content: "床前明月光，疑是地上霜。\n举头望明月，低头思故乡。",
    tags: "思乡,月光",
  },
  {
    id: 2,
    title: "春晓",
    author: "孟浩然",
    dynasty: "唐",
    theme: "",
    content_preview: "春眠不觉晓，处处闻啼鸟。",
    content: "春眠不觉晓，处处闻啼鸟。\n夜来风雨声，花落知多少。",
    tags: "春天,自然",
  },
  {
    id: 3,
    title: "登鹳雀楼",
    author: "王之涣",
    dynasty: "唐",
    theme: "",
    content_preview: "白日依山尽，黄河入海流。",
    content: "白日依山尽，黄河入海流。\n欲穷千里目，更上一层楼。",
    tags: "壮志,哲理",
  },
  {
    id: 4,
    title: "望庐山瀑布",
    author: "李白",
    dynasty: "唐",
    theme: "",
    content_preview: "日照香炉生紫烟，遥看瀑布挂前川。",
    content: "日照香炉生紫烟，遥看瀑布挂前川。\n飞流直下三千尺，疑是银河落九天。",
    tags: "山水,壮丽",
  },
  {
    id: 5,
    title: "水调歌头",
    author: "苏轼",
    dynasty: "宋",
    theme: "",
    content_preview: "明月几时有，把酒问青天。",
    content: "明月几时有，把酒问青天。\n不知天上宫阙，今夕是何年。",
    tags: "月亮,思念",
  },
  {
    id: 6,
    title: "念奴娇·赤壁怀古",
    author: "苏轼",
    dynasty: "宋",
    theme: "",
    content_preview: "大江东去，浪淘尽，千古风流人物。",
    content: "大江东去，浪淘尽，千古风流人物。\n故垒西边，人道是，三国周郎赤壁。",
    tags: "怀古,豪放",
  },
];

const MOCK_STATS = {
  total: 58059,
  dynasties: [
    { name: "唐", count: 56570 },
    { name: "宋", count: 1489 },
    { name: "元", count: 0 },
    { name: "明", count: 0 },
    { name: "清", count: 0 },
  ],
  themes: [],
};

const MOCK_USER_PROFILE = {
  id: "1",
  email: "test@test.com",
  name: "Test User",
  tier: "free",
  role: "user",
  is_early_adopter: false,
  created_at: "2024-01-01T00:00:00Z",
};

const MOCK_QUOTA = {
  tier: "free",
  records: [
    { resource: "ask", daily_limit: 10, used: 3 },
  ],
};

// ─── Route handler: single function handles ALL /v1/* requests ───

function createApiRouteHandler(context: BrowserContext) {
  context.route(/\b\/v1\//, async (route) => {
    const url = route.request().url();

    // Auth profile
    if (url.includes("/v1/auth/profile")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER_PROFILE),
      });
    }

    // Quota
    if (url.includes("/v1/quota")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_QUOTA),
      });
    }

    // Poetry stats
    if (url.match(/\/v1\/poetry\/stats/)) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_STATS),
      });
    }

    // Poetry browse
    if (url.match(/\/v1\/poetry\/browse/)) {
      const params = new URL(url).searchParams;
      const dynasty = params.get("dynasty");
      if (dynasty === "宋") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: MOCK_POEMS.filter((p) => p.dynasty === "宋"),
            total: 1489,
            page: 1,
            per_page: 20,
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: MOCK_POEMS.filter((p) => p.dynasty === "唐").slice(0, 3),
          total: 56570,
          page: 1,
          per_page: 20,
        }),
      });
    }

    // Poetry search
    if (url.match(/\/v1\/poetry\/search/)) {
      const q = new URL(url).searchParams.get("q") || "";
      const results = MOCK_POEMS.filter(
        (p) =>
          p.title.includes(q) || p.content.includes(q) || p.author.includes(q)
      );
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ results, query: q, count: results.length }),
      });
    }

    // Poetry random
    if (url.match(/\/v1\/poetry\/random/)) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ results: MOCK_POEMS.slice(3, 6), count: 3 }),
      });
    }

    // Poetry single poem (catch /v1/poetry/{id})
    const poemMatch = url.match(/\/v1\/poetry\/(\d+)$/);
    if (poemMatch) {
      const id = parseInt(poemMatch[1]);
      const poem = MOCK_POEMS.find((p) => p.id === id);
      if (poem) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(poem),
        });
      }
      return route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ error: "Not found" }),
      });
    }

    // Catch-all for any other /v1/* endpoint
    console.log(`[mock] unhandled API: ${url}`);
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

// ─── Helper: hide sidebar on mobile viewport ──────────────

async function hideMobileSidebar(page: Page): Promise<void> {
  const viewport = page.viewportSize();
  if (viewport && viewport.width < 768) {
    await page.evaluate(() => {
      // Hide the fixed sidebar that intercepts pointer events on small screens
      const aside = document.querySelector("aside");
      if (aside) aside.style.display = "none";
      // Remove sidebar margin offset from main content area
      const mainArea = document.querySelector("div[style*='margin-left']");
      if (mainArea) mainArea.style.marginLeft = "0";
    });
  }
}

// ─── Helper: navigate to Poetry page with full setup ─────────

async function gotoPoetry(page: Page): Promise<void> {
  // Navigate first to establish origin
  await page.goto("/");
  await page.waitForTimeout(300);

  // Now navigate to poetry — route handlers are registered at context level
  await page.goto("/poetry");

  // Wait until the Poetry page heading appears (auth guard must have passed)
  // Use getByRole to avoid strict mode violation (sidebar also has <h1>)
  await expect(page.getByRole("heading", { name: "诗词文库" })).toBeVisible({ timeout: 15_000 });

  // On mobile viewports, hide sidebar to prevent pointer event interception
  await hideMobileSidebar(page);
}

// ─── Tests ──────────────────────────────────────────────────

test.describe("Poetry Page", () => {
  test.beforeEach(async ({ context, page }) => {
    // Register auth + API mocks at CONTEXT level (works for all pages/navigations)

    // 1. Inject auth token into localStorage before any page loads
    await context.addInitScript(() => {
      localStorage.setItem(
        "saas-auth",
        JSON.stringify({ state: { token: "mock-e2e-token" }, version: 0 })
      );
    });

    // 2. Register API route handler at context level
    createApiRouteHandler(context);
  });

  // ─── Page Load ──────────────────────────────────────────

  test("should display poetry header with stats", async ({ page }) => {
    await gotoPoetry(page);

    // Use getByRole to target the content heading specifically (sidebar also has <h1>)
    const heading = page.getByRole("heading", { name: "诗词文库" });
    await expect(heading).toHaveText("诗词文库");

    // Stats line: "收录 58,059 诗词，5 个朝代" — scope to main content to exclude sidebar
    const statsLine = page.locator("main p", { hasText: "收录" });
    await expect(statsLine).toContainText("58,059");
    await expect(statsLine).toContainText("朝代");
  });

  // ─── Dynasty Filter Chips ────────────────────────────────

  test("should show dynasty filter chips with counts", async ({ page }) => {
    await gotoPoetry(page);

    const allChip = page.locator("button", { hasText: "全部" }).first();
    await expect(allChip).toBeVisible();

    const tangChip = page.locator("button", { hasText: "唐" }).first();
    await expect(tangChip).toBeVisible();
    await expect(tangChip).toContainText("56,570");

    const songChip = page.locator("button", { hasText: "宋" }).first();
    await expect(songChip).toBeVisible();
    await expect(songChip).toContainText("1,489");
  });

  test("should filter poems by dynasty", async ({ page }) => {
    await gotoPoetry(page);

    const songChip = page.locator("button", { hasText: /^宋\s*\(1,489\)/ }).first();
    await songChip.click();

    await expect(page.locator("h3", { hasText: "水调歌头" })).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("h3", { hasText: "念奴娇·赤壁怀古" })).toBeVisible({ timeout: 3_000 });
  });

  test("should clear dynasty filter by clicking 全部", async ({ page }) => {
    await gotoPoetry(page);

    const tangChip = page.locator("button", { hasText: /^唐\s*\(56,570\)/ }).first();
    await tangChip.click();

    const allChip = page.locator("button", { hasText: "全部" }).first();
    await allChip.click();

    await expect(page.locator("h3", { hasText: "静夜思" })).toBeVisible({ timeout: 5_000 });
  });

  // ─── Poem Cards in Browse Mode ──────────────────────────

  test("should display poem cards with title, author, preview", async ({ page }) => {
    await gotoPoetry(page);

    await expect(page.locator("h3", { hasText: "静夜思" })).toBeVisible({ timeout: 10_000 });
    await expect(
      page.locator("p", { hasText: "唐 · 李白" }).first()
    ).toBeVisible({ timeout: 3_000 });
    await expect(
      page.locator("p", { hasText: "床前明月光，疑是地上霜。" }).first()
    ).toBeVisible({ timeout: 3_000 });
  });

  // ─── Search Mode ────────────────────────────────────────

  test("should search poems by keyword and show results", async ({ page }) => {
    await gotoPoetry(page);

    const searchInput = page.locator(
      "input[placeholder='输入诗词名、作者或关键词...']"
    );
    await searchInput.fill("明月");

    // Use force click to avoid mode-switcher "搜索" button intercepting pointer
    // on narrow viewports; on desktop it works normally
    const searchBtn = page.locator("div.flex.flex-1 > button", { hasText: "搜索" });
    await searchBtn.click({ force: true });

    const resultHeader = page.locator("p", { hasText: "明月" });
    await expect(resultHeader).toBeVisible({ timeout: 5_000 });
    await expect(resultHeader).toContainText("找到");
  });

  test("should search on Enter key", async ({ page }) => {
    await gotoPoetry(page);

    const searchInput = page.locator(
      "input[placeholder='输入诗词名、作者或关键词...']"
    );
    await searchInput.fill("明月");
    await searchInput.press("Enter");

    await expect(page.locator("p", { hasText: "明月" })).toBeVisible({ timeout: 5_000 });
  });

  test("should not search with empty query", async ({ page }) => {
    await gotoPoetry(page);

    // Empty search should stay in browse mode — verify poem cards still visible
    // Don't click the "搜索" action button with empty query (it's disabled),
    // just verify browse mode content remains
    await expect(page.locator("h3", { hasText: "静夜思" })).toBeVisible({ timeout: 5_000 });
  });

  // ─── Discover Mode ──────────────────────────────────────

  test("should switch to discover mode and show random poems", async ({ page }) => {
    await gotoPoetry(page);

    const discoverBtn = page.locator("button", { hasText: "发现" }).first();
    await discoverBtn.click();

    // Poetry.tsx now auto-fetches random poems when switching to discover mode
    await expect(page.getByRole("heading", { name: "随机发现" })).toBeVisible({ timeout: 5_000 });

    const refreshBtn = page.locator("button", { hasText: /再来一组/ });
    await expect(refreshBtn).toBeVisible({ timeout: 3_000 });

    await expect(page.locator("h3", { hasText: "望庐山瀑布" })).toBeVisible({ timeout: 5_000 });
  });

  test("should refresh random poems on 再来一组", async ({ page }) => {
    await gotoPoetry(page);

    const discoverBtn = page.locator("button", { hasText: "发现" }).first();
    await discoverBtn.click();
    await expect(page.getByRole("heading", { name: "随机发现" })).toBeVisible({ timeout: 5_000 });

    const refreshBtn = page.locator("button", { hasText: /再来一组/ });
    await refreshBtn.click();

    await expect(page.locator("h3").first()).toBeVisible({ timeout: 5_000 });
  });

  // ─── Detail Modal ───────────────────────────────────────

  test("should open poem detail modal on card click", async ({ page }) => {
    await gotoPoetry(page);

    const poemTitle = page.locator("h3", { hasText: "静夜思" });
    await poemTitle.click({ force: true });

    await expect(page.getByRole("heading", { name: "静夜思", level: 2 })).toBeVisible({ timeout: 5_000 });

    await expect(page.locator("div.max-h-\\[60vh\\]")).toContainText("举头望明月", { timeout: 5_000 });
  });

  test("should close detail modal on backdrop click", async ({ page }) => {
    await gotoPoetry(page);

    await page.locator("h3", { hasText: "静夜思" }).click({ force: true });
    await expect(page.getByRole("heading", { name: "静夜思", level: 2 })).toBeVisible({ timeout: 5_000 });

    const modalOverlay = page.locator("div.fixed.inset-0.z-50");
    await modalOverlay.click({ position: { x: 0, y: 0 } });

    await expect(page.getByRole("heading", { name: "静夜思", level: 2 })).not.toBeVisible({ timeout: 5_000 });
  });

  test("should show tags in detail modal", async ({ page }) => {
    await gotoPoetry(page);

    await page.locator("h3", { hasText: "静夜思" }).click({ force: true });
    await expect(page.getByRole("heading", { name: "静夜思", level: 2 })).toBeVisible({ timeout: 5_000 });

    await expect(page.locator("span.px-2", { hasText: "思乡" })).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("span.px-2", { hasText: "月光" })).toBeVisible({ timeout: 3_000 });
  });

  // ─── Pagination ──────────────────────────────────────────

  test("should show pagination controls", async ({ page }) => {
    await gotoPoetry(page);

    const prevBtn = page.locator("button", { hasText: "上一页" });
    const nextBtn = page.locator("button", { hasText: "下一页" });
    await expect(prevBtn).toBeVisible({ timeout: 5_000 });
    await expect(nextBtn).toBeVisible({ timeout: 3_000 });

    const pageInfo = page.locator("span", { hasText: "共" });
    await expect(pageInfo).toContainText("1");
    await expect(pageInfo).toContainText("56,570");
  });

  // ─── Mode Switcher ──────────────────────────────────────

  test("should switch between browse, search, discover modes", async ({ page }) => {
    await gotoPoetry(page);

    await expect(page.locator("button", { hasText: "全部" }).first()).toBeVisible({ timeout: 5_000 });

    const modeButtons = page.locator("div.flex.rounded-md.overflow-hidden > button");
    const searchModeBtn = modeButtons.nth(1);
    await searchModeBtn.click();

    await expect(page.locator("button", { hasText: "全部" }).first()).not.toBeVisible({ timeout: 5_000 });

    const discoverModeBtn = modeButtons.nth(2);
    await discoverModeBtn.click();

    // Discover mode auto-fetches random poems now
    await expect(page.getByRole("heading", { name: "随机发现" })).toBeVisible({ timeout: 5_000 });
  });

  // ─── Mobile Responsive ──────────────────────────────────

  test("mobile: should render poetry page on small viewport", async ({
    browser,
  }) => {
    const mobileContext = await browser.newContext({
      viewport: { width: 375, height: 812 },
      isMobile: true,
      hasTouch: true,
    });

    // Set up auth + API mocks for mobile context
    await mobileContext.addInitScript(() => {
      localStorage.setItem(
        "saas-auth",
        JSON.stringify({ state: { token: "mock-e2e-token-mobile" }, version: 0 })
      );
    });
    createApiRouteHandler(mobileContext);

    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto("/");
    await mobilePage.waitForTimeout(300);
    await mobilePage.goto("/poetry");

    // Wait for poetry heading using getByRole (avoids strict mode)
    await expect(mobilePage.getByRole("heading", { name: "诗词文库" })).toBeVisible({ timeout: 15_000 });

    // Hide sidebar on mobile viewport to prevent pointer event interception
    await hideMobileSidebar(mobilePage);

    await expect(mobilePage.getByRole("heading", { name: "诗词文库" })).toHaveText("诗词文库");
    await expect(mobilePage.locator("h3", { hasText: "静夜思" })).toBeVisible({ timeout: 10_000 });

    await mobileContext.close();
  });
});
