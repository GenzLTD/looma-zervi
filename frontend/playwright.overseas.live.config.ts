import { defineConfig, devices } from "@playwright/test";
import path from "path";

const repoRoot = path.resolve(__dirname, "..");

/**
 * Overseas B2C SaaS E2E — genz-web 官网 + SaaS 工作台 + api.genz.ltd
 *
 * Usage:
 *   # 全链路（本地 dev server + 本地后端）
 *   pnpm e2e:overseas
 *
 *   # 生产环境线上测试（跳过 webServer，直接打线上 URL）
 *   E2E_OVERSEAS_WEB=https://genz.ltd \
 *   E2E_OVERSEAS_SAAS=https://app.genz.ltd \
 *   E2E_OVERSEAS_API=https://api.genz.ltd \
 *   pnpm e2e:overseas
 *
 *   # 单测
 *   pnpm e2e:overseas -- --grep "Free button"
 */

const IS_PRODUCTION =
  !!process.env.E2E_OVERSEAS_WEB &&
  !!process.env.E2E_OVERSEAS_SAAS &&
  !!process.env.E2E_OVERSEAS_API &&
  !process.env.E2E_OVERSEAS_API.includes("localhost") &&
  !process.env.E2E_OVERSEAS_API.includes("127.0.0.1");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/overseas-closed-loop.live.spec.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "html",
  timeout: 90_000,
  expect: { timeout: 15_000 },

  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "overseas",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],

  // Production mode: skip webServer entirely (targets are live URLs)
  // Local mode: start backend + genz-web + saas dev servers
  webServer: IS_PRODUCTION
    ? []
    : [
        {
          command: `bash ${path.join(repoRoot, "scripts/e2e-backend.sh")}`,
          url: `${process.env.E2E_OVERSEAS_API ?? "http://127.0.0.1:5200"}/health`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
        {
          command: "pnpm dev:genz-web",
          url: "http://localhost:5180",
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
        {
          command: `VITE_API_BASE=${process.env.E2E_OVERSEAS_API ?? "http://127.0.0.1:5200"} pnpm dev:saas`,
          url: "http://localhost:5174",
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      ],
});
