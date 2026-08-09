import { defineConfig } from "@playwright/test";
import path from "path";

const repoRoot = path.resolve(__dirname, "..");

/**
 * Overseas API-only live tests (no SaaS/genz-web browser).
 *
 * Includes P0 (jobs/resume/trust) + P1 API (consent/poetry/candidates.api).
 * Browser candidates UI is NOT here — use playwright.overseas.live.config.ts.
 *
 * Usage:
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:p0      # 11 tests
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:p1-api
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:api    # all API specs
 */

const apiBase = process.env.E2E_OVERSEAS_API ?? "https://api.genz.ltd";
const IS_LOCAL =
  apiBase.includes("localhost") || apiBase.includes("127.0.0.1");

export default defineConfig({
  testDir: "./e2e",
  testMatch: [
    "**/jobs-match.live.spec.ts",
    "**/resume-parse.live.spec.ts",
    "**/trust.live.spec.ts",
    "**/consent-full.live.spec.ts",
    "**/poetry-challenge.live.spec.ts",
    "**/candidates-overseas.api.live.spec.ts",
  ],
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 180_000,
  expect: { timeout: 30_000 },

  use: {
    // API-only: no baseURL / browser required, but Playwright still boots a project.
    trace: "off",
  },

  projects: [
    {
      name: "overseas-api",
    },
  ],

  webServer: IS_LOCAL
    ? [
        {
          command: `bash ${path.join(repoRoot, "scripts/e2e-backend.sh")}`,
          url: `${apiBase}/health`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      ]
    : [],
});
