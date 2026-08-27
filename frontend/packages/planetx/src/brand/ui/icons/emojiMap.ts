/**
 * Icon name → common emoji migration map (optional helpers).
 * Prefer <PlanetXIcon name="…" /> over emoji in new UI.
 */
import type { PlanetXIconName } from "./glyphs";

export const EMOJI_TO_ICON: Partial<Record<string, PlanetXIconName>> = {
  "🚀": "rocket",
  "✨": "spark",
  "🎯": "target",
  "👥": "fleet",
  "🪪": "profile",
  "👤": "profile",
  "🏆": "trophy",
  "⭐": "star",
  "🌌": "planet",
  "📡": "signal",
  "🤝": "handshake",
  "🔮": "crystal",
  "🌀": "timeline",
  "ℹ️": "info",
  "✓": "check",
  "✅": "check",
  "⚠": "warning",
  "⚠️": "warning",
  "✗": "error",
  "❌": "error",
  "⚙️": "settings",
  "🚪": "logout",
  "✏️": "edit",
  "🗑️": "trash",
  "🛡️": "shield",
  "▼": "chevron-down",
  "▲": "chevron-up",
  "←": "chevron-left",
  "→": "chevron-right",
};
