/**
 * E2E API 基址守卫。
 *
 * 背景（2026-09-16 定位）：
 * overseasApi.ts 曾默认 `https://api.genz.ltd`，而 playwright.overseas.live.config.ts
 * 的 webServer 默认拉起的是本地后端。两者不一致导致「本地模式」跑 E2E 时，
 * 注册请求被打到生产库，生产 users 表因此累积了 157 个 @test.local 账号。
 *
 * 本地模式的 E2E 后端使用独立库 backend/data/e2e-playwright.db，
 * 且 scripts/e2e-backend.sh 每次运行前 `rm -f` 重建 —— 本地跑天然不污染生产。
 * 所以这里的默认值必须与 config 的 webServer 保持一致。
 */

const LOCAL_PATTERN =
  /^https?:\/\/(127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])(:\d+)?(\/|$)/;

export function isLocalApi(base: string): boolean {
  return LOCAL_PATTERN.test(base);
}

/**
 * 非本地 API 必须显式 opt-in，否则直接抛错。
 *
 * 抛错的目的是让误用**在测试开始前**失败，而不是静默往真实库里写数据。
 */
export function assertLocalApi(base: string, envVar: string): void {
  if (isLocalApi(base)) return;
  if (process.env.E2E_ALLOW_REMOTE_API === "1") return;

  throw new Error(
    [
      `E2E 拒绝指向非本地 API：${base}（来自 ${envVar}）`,
      "",
      "本地跑 E2E 请留空该环境变量，默认 127.0.0.1:5200。",
      "该后端使用独立库 backend/data/e2e-playwright.db，每次运行前重建，",
      "不会污染生产数据。",
      "",
      "确需对远程/生产环境跑，请显式设置 E2E_ALLOW_REMOTE_API=1，",
      "并提供 E2E_ADMIN_TOKEN 以便 globalTeardown 回收测试账号，",
      "否则账号会注册进真实库且无法自动清理。",
    ].join("\n"),
  );
}
