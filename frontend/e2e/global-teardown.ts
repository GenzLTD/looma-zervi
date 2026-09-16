/**
 * Playwright globalTeardown —— 回收本轮 E2E 注册的测试账号。
 *
 * 本地模式通常不需要清理：scripts/e2e-backend.sh 启动时会 `rm -f`
 * 独立库 backend/data/e2e-playwright.db，账号随库一起消失。
 *
 * 但当 E2E_ALLOW_REMOTE_API=1 指向真实库时必须清理，否则测试账号会持续
 * 累积（历史上生产库就这样积了 157 个 @test.local）。
 *
 * 清理走 admin 接口 POST /v1/admin/test-accounts/purge，需要 admin JWT：
 *   E2E_ADMIN_TOKEN=<登录 beta_admin 等 admin 账号得到的 access_token>
 * 该接口只接受测试域名后缀，永不触碰真人账号，也永不删除 seed 的 beta_*。
 *
 * 本函数永不抛错 —— 清理失败不应让测试结果变成失败。
 */

const TEST_SUFFIXES = [
  "@test.local",
  "@test.com",
  "@example.com",
  "@looma-test.internal",
  "@genz-test.ltd",
];

function isLocal(base: string): boolean {
  return /^https?:\/\/(127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])(:\d+)?(\/|$)/.test(base);
}

export default async function globalTeardown(): Promise<void> {
  const apiBase = process.env.E2E_OVERSEAS_API ?? process.env.E2E_API_BASE ?? "";
  const token = process.env.E2E_ADMIN_TOKEN;

  if (!apiBase) {
    return;
  }

  if (!token) {
    if (isLocal(apiBase)) {
      console.log(
        "[e2e-teardown] 本地库无需清理（scripts/e2e-backend.sh 下次启动会重建）。",
      );
    } else {
      console.warn(
        [
          "[e2e-teardown] 未设置 E2E_ADMIN_TOKEN，测试账号不会被回收。",
          `本轮指向 ${apiBase}，账号将残留在真实库中。`,
          `可手动清理：POST ${apiBase}/v1/admin/test-accounts/purge`,
        ].join("\n"),
      );
    }
    return;
  }

  try {
    const resp = await fetch(`${apiBase}/v1/admin/test-accounts/purge`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ suffixes: TEST_SUFFIXES }),
    });

    const text = await resp.text();
    if (!resp.ok) {
      console.warn(`[e2e-teardown] 清理失败 (${resp.status}): ${text}`);
      return;
    }
    console.log(`[e2e-teardown] 已回收测试账号: ${text}`);
  } catch (err) {
    console.warn(`[e2e-teardown] 清理请求异常（已忽略）: ${String(err)}`);
  }
}
