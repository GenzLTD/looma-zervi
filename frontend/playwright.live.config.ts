import { defineConfig, devices } from "@playwright/test";
import path from "path";

const repoRoot = path.resolve(__dirname, "..");
const apiBase = process.env.E2E_API_BASE ?? "http://127.0.0.1:5200";

/**
 * Playwright E2E against live Flask backend (no API mocks).
 *
 * Usage:
 *   pnpm e2e:live              — SaaS closed-loop
 *   pnpm e2e:live:all          — SaaS + PlanetX
 *
 * Requires: backend venv + poetry_full data (script starts backend automatically).
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.live.spec.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "html",
  timeout: 90_000,
  expect: { timeout: 15_000 },

  // 回收测试账号（本地库会被 e2e-backend.sh 重建，此处主要服务于远程/生产模式）
  globalTeardown: path.join(__dirname, "e2e/global-teardown.ts"),

  use: {
    baseURL: "http://localhost:5174",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "live-saas",
      testMatch: "**/closed-loop.live.spec.ts",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "live-consent",
      testMatch: "**/consent.live.spec.ts",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "live-planetx",
      testMatch: "**/planetx-share.live.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:5173",
      },
    },
  ],

  webServer: [
    {
      command: `bash ${path.join(repoRoot, "scripts/e2e-backend.sh")}`,
      url: `${apiBase}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `VITE_API_BASE=${apiBase} pnpm dev:saas`,
      url: "http://localhost:5174",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `VITE_API_BASE=${apiBase} VITE_SAAS_URL=http://localhost:5174 pnpm dev:planetx`,
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
