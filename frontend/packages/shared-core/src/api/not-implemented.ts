/**
 * resume.v1.json v0.1.0 — not_implemented_convention 的客户端唯一判定入口。
 *
 * 契约真源: looma-zervi/backend/contracts/resume.v1.json#not_implemented_convention
 *
 * 2026-10-29 契约收口（阶段3 八端点全部 implemented；transition_405.whitelist 已清空，
 * 并写入 closed_at / expiry=已到期）之后的判定口径：
 *  - 只有 501 + error==='not_implemented' 视为「契约声明未实现」
 *  - 405 一律按真实错误处理：白名单随阶段3 收口清空，客户端不得再把 405 降级成
 *    「功能建设中」——否则真 bug（如对 /list 发 PUT）会被静默吞掉，且再没有到期日
 *  - 页面/工厂禁止各自判断，一律走本函数
 */

/** 兼容 web/mini 两个 ApiError 面（body vs details），以及普通 object 形态的错误 */
function readErrorField(err: any, key: string): any {
  return err?.body?.[key] ?? err?.details?.[key] ?? err?.[key];
}

/**
 * 判定 err 是否为「契约声明未实现」。
 *
 * 只需错误对象本身：405 白名单移除后不再需要 method/path 上下文
 * （MiniApiClient 仍在 details 里附 __method/__path，仅作日志诊断用）。
 */
export function isNotImplemented(err: unknown): boolean {
  const e = err as any;
  if (!e || typeof e !== "object") return false;

  const status = readErrorField(e, "status");
  const errorCode = readErrorField(e, "error");

  return status === 501 && errorCode === "not_implemented";
}
