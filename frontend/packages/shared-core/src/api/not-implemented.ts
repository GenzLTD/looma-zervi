/**
 * resume.v1.json v0.1.0 — not_implemented_convention 的客户端唯一判定入口。
 *
 * 契约真源: looma-zervi/backend/contracts/resume.v1.json#not_implemented_convention
 * 裁决 2026-10-29:
 *  - 501 + error==='not_implemented' → 真（阶段3 前的预期形态）
 *  - 405 仅当 method+path 命中 transition_405.whitelist 时降级为真，并打 warn 日志；
 *    白名单外的 405 一律按真实错误处理（如对 /list 发 PUT 这类真 bug 不许静默吞掉）
 *  - 页面/工厂禁止各自判断，一律走本函数
 *  - 阶段3 stub handler（网关 any() → 501）上线后应删除 405 分支
 */

/** resume.v1.json#not_implemented_convention.transition_405.whitelist（8 端点） */
// GET /v1/resume/:resume_id 需排除已实现的静态段（list/analysis/parse/upload/ingest/improve），
// 否则对 /list、/analysis 的真 405 会被吞掉（复验裁决 2026-10-29）。
// 交替加 (?:…)$ 分组锚定：原写法 $ 只作用于最后一个分支，会把 /listxxx 一并排除（无害但语义不准）。
const IMPLEMENTED_STATIC_SEGMENTS = "(?:list|analysis|parse|upload|ingest|improve)$";
const STUB_501_WHITELIST: Array<{ method: string; pattern: RegExp }> = [
  { method: "GET", pattern: `^/v1/resume/(?!${IMPLEMENTED_STATIC_SEGMENTS})[^/]+$` },
  { method: "PUT", pattern: "^/v1/resume/[^/]+$" },
  { method: "GET", pattern: "^/v1/resume/[^/]+/permission$" },
  { method: "PUT", pattern: "^/v1/resume/[^/]+/permission$" },
  { method: "GET", pattern: "^/v1/resume/blacklist$" },
  { method: "POST", pattern: "^/v1/resume/blacklist$" },
  { method: "DELETE", pattern: "^/v1/resume/blacklist/[^/]+$" },
  { method: "GET", pattern: "^/v1/resume/templates$" },
].map((e) => ({ method: e.method, pattern: new RegExp(e.pattern) }));

function matchesWhitelist(method: string, path: string): boolean {
  const upper = method.toUpperCase();
  // 去掉 query string，与契约 whitelist 的纯路径语义对齐
  const clean = path.split("?")[0];
  return STUB_501_WHITELIST.some(
    (e) => e.method === upper && e.pattern.test(clean)
  );
}

/** 兼容 web/mini 两个 ApiError 面（body vs details），以及普通 object 形态的错误 */
function readErrorField(err: any, key: string): any {
  return err?.body?.[key] ?? err?.details?.[key] ?? err?.[key];
}

/**
 * 判定 err 是否为「契约声明未实现」。
 *
 * @param err catch 到的错误（ApiError 或普通对象）
 * @param req  可选请求上下文。MiniApiClient 抛错时已把 method/path 附进 details，
 *             通常无需传；Web 面或自定义错误可显式传入以保证 405 白名单判定可用。
 */
export function isNotImplemented(err: unknown, req?: { method: string; path: string }): boolean {
  const e = err as any;
  if (!e || typeof e !== "object") return false;

  const status = readErrorField(e, "status");
  const errorCode = readErrorField(e, "error");

  // 主判定：501 + not_implemented（契约固定形态）
  if (status === 501 && errorCode === "not_implemented") return true;

  // 过渡期兜底：405 仅在 stub_501 白名单内降级（打 warn 便于统计残留）
  if (status === 405) {
    const method = String(req?.method ?? readErrorField(e, "__method") ?? "");
    const path = String(req?.path ?? readErrorField(e, "__path") ?? "");
    if (method && path && matchesWhitelist(method, path)) {
      console.warn(
        `[resume-contract] 405 降级为未实现（过渡期兜底，阶段3 stub 上线后删除）: ${method} ${path}`
      );
      return true;
    }
  }

  return false;
}
