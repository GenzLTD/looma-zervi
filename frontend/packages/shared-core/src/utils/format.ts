/**
 * Formatting utilities shared across brands.
 */

/**
 * iOS/旧 WebView 的 Date 解析不接受 "YYYY-MM-DD HH:mm:ss"（空格分隔），
 * 后端时间戳正是这种格式。统一在解析前把首个空格换成 "T"。
 */
function parseDate(date: string | Date): Date {
  if (date instanceof Date) return date;
  return new Date(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(date) ? date.replace(" ", "T") : date);
}

export function formatDate(date: string | Date, locale = "zh-CN"): string {
  const d = parseDate(date);
  return d.toLocaleDateString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatDateTime(date: string | Date, locale = "zh-CN"): string {
  const d = parseDate(date);
  return d.toLocaleString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("zh-CN").format(n);
}

export function formatRelativeTime(date: string | Date): string {
  const d = parseDate(date);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return "刚刚";
  if (minutes < 60) return `${minutes}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  if (days < 30) return `${days}天前`;
  return formatDate(d);
}

export function truncate(text: string, maxLength: number, suffix = "..."): string {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength - suffix.length) + suffix;
}

export function formatPercent(value: number, fractionDigits = 1): string {
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
