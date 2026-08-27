/**
 * PlanetX icon registry — stroke SVG, color via currentColor → CSS tokens.
 *
 * Figma 情绪板「图标风格」目前只有参考图，无独立可导出组件集；
 * 本批为可替换的 interim glyphs，后续设计师交付 SVG 时按同名替换即可。
 */

export type PlanetXIconName =
  | "rocket"
  | "spark"
  | "target"
  | "fleet"
  | "profile"
  | "trophy"
  | "star"
  | "planet"
  | "signal"
  | "handshake"
  | "crystal"
  | "timeline"
  | "info"
  | "check"
  | "warning"
  | "error"
  | "close"
  | "chevron-down"
  | "chevron-up"
  | "chevron-left"
  | "chevron-right"
  | "settings"
  | "logout"
  | "edit"
  | "trash"
  | "shield"
  | "copy"
  | "share"
  | "spinner";

type GlyphProps = {
  size: number;
  strokeWidth: number;
};

function SvgRoot({
  size,
  strokeWidth,
  children,
}: GlyphProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      style={{ display: "block", flexShrink: 0 }}
    >
      <g
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {children}
      </g>
    </svg>
  );
}

export const ICON_GLYPHS: Record<PlanetXIconName, (p: GlyphProps) => React.ReactNode> = {
  rocket: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M5 15c2-1 4-1.5 6-3.5 2.5-2.5 3.5-5.5 4-8.5-3 .5-6 1.5-8.5 4C4.5 9 4 11 5 15Z" />
      <path d="M9.5 14.5 5 19" />
      <path d="M14.5 9.5 19 5" />
      <circle cx="14.2" cy="9.8" r="1.2" fill="currentColor" stroke="none" />
    </SvgRoot>
  ),
  spark: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
    </SvgRoot>
  ),
  target: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
    </SvgRoot>
  ),
  fleet: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <circle cx="9" cy="8" r="3" />
      <circle cx="16.5" cy="9.5" r="2.5" />
      <path d="M3.5 19c.8-3 3-5 5.5-5s4.7 2 5.5 5" />
      <path d="M13 19c.5-2 1.8-3.5 3.5-3.5 1.4 0 2.6.9 3.2 2.3" />
    </SvgRoot>
  ),
  profile: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <rect x="4" y="5" width="16" height="14" rx="2.5" />
      <circle cx="10" cy="11" r="2.2" />
      <path d="M14 9.5h4M14 12.5h3.5M7 16.5h10" />
    </SvgRoot>
  ),
  trophy: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M8 5h8v4.5a4 4 0 0 1-8 0V5Z" />
      <path d="M8 7H5.5A2.5 2.5 0 0 0 8 9.5" />
      <path d="M16 7h2.5A2.5 2.5 0 0 1 16 9.5" />
      <path d="M12 13.5V16" />
      <path d="M9 19h6" />
      <path d="M10 16h4v3H10z" />
    </SvgRoot>
  ),
  star: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M12 3.5 14.2 9l5.8.5-4.4 3.7 1.4 5.6L12 15.8 6.9 18.8l1.4-5.6L4 9.5 9.8 9 12 3.5Z" />
    </SvgRoot>
  ),
  planet: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <circle cx="12" cy="12" r="6.5" />
      <ellipse cx="12" cy="12" rx="10" ry="3.2" transform="rotate(-24 12 12)" />
    </SvgRoot>
  ),
  signal: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M5 16a9 9 0 0 1 14 0" />
      <path d="M7.5 13.5a5.5 5.5 0 0 1 9 0" />
      <path d="M10 11a2.5 2.5 0 0 1 4 0" />
      <circle cx="12" cy="17.5" r="1.2" fill="currentColor" stroke="none" />
    </SvgRoot>
  ),
  handshake: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M8 11 4.5 9.5 3 12.5l4 2.5 3-2" />
      <path d="M16 11 19.5 9.5 21 12.5l-4 2.5-3-2" />
      <path d="M8.5 13.5 11 16l2-1.5 2.5 1.5 1.5-2.5" />
      <path d="M9 8.5h6" />
    </SvgRoot>
  ),
  crystal: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M12 3 17 9l-5 12L7 9 12 3Z" />
      <path d="M7 9h10" />
      <path d="M12 3v18" />
    </SvgRoot>
  ),
  timeline: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M7 4v16" />
      <circle cx="7" cy="7" r="2" />
      <circle cx="7" cy="12" r="2" />
      <circle cx="7" cy="17" r="2" />
      <path d="M11 7h8M11 12h6M11 17h7" />
    </SvgRoot>
  ),
  info: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 11v5" />
      <circle cx="12" cy="8" r="1" fill="currentColor" stroke="none" />
    </SvgRoot>
  ),
  check: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M5 12.5 10 17.5 19 7" />
    </SvgRoot>
  ),
  warning: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M12 4 21 19H3L12 4Z" />
      <path d="M12 10v4" />
      <circle cx="12" cy="16.5" r="1" fill="currentColor" stroke="none" />
    </SvgRoot>
  ),
  error: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <circle cx="12" cy="12" r="8" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </SvgRoot>
  ),
  close: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="m7 7 10 10M17 7 7 17" />
    </SvgRoot>
  ),
  "chevron-down": ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="m6 9 6 6 6-6" />
    </SvgRoot>
  ),
  "chevron-up": ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="m6 15 6-6 6 6" />
    </SvgRoot>
  ),
  "chevron-left": ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="m15 6-6 6 6 6" />
    </SvgRoot>
  ),
  "chevron-right": ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="m9 6 6 6-6 6" />
    </SvgRoot>
  ),
  settings: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3.5v2.2M12 18.3V20.5M4.8 6.5l1.6 1.6M17.6 15.9l1.6 1.6M3.5 12h2.2M18.3 12h2.2M4.8 17.5l1.6-1.6M17.6 8.1l1.6-1.6" />
    </SvgRoot>
  ),
  logout: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M10 5H6.5A2.5 2.5 0 0 0 4 7.5v9A2.5 2.5 0 0 0 6.5 19H10" />
      <path d="M14 8l4 4-4 4M9 12h9" />
    </SvgRoot>
  ),
  edit: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3Z" />
      <path d="m13.5 6.5 3 3" />
    </SvgRoot>
  ),
  trash: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M5 8h14" />
      <path d="M9 8V6.5A1.5 1.5 0 0 1 10.5 5h3A1.5 1.5 0 0 1 15 6.5V8" />
      <path d="M7.5 8 8.3 19h7.4l.8-11" />
    </SvgRoot>
  ),
  shield: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M12 3.5 19 7v5.5c0 4.2-2.8 7.5-7 8.5-4.2-1-7-4.3-7-8.5V7l7-3.5Z" />
      <path d="m9.5 12 1.8 1.8 3.7-3.8" />
    </SvgRoot>
  ),
  copy: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <rect x="8" y="8" width="11" height="11" rx="2" />
      <path d="M6 15.5V6.5A2.5 2.5 0 0 1 8.5 4H15" />
    </SvgRoot>
  ),
  share: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <circle cx="6.5" cy="12" r="2.2" />
      <circle cx="17" cy="6.5" r="2.2" />
      <circle cx="17" cy="17.5" r="2.2" />
      <path d="m8.4 11 6-3.2M8.5 13.2l6 3.1" />
    </SvgRoot>
  ),
  spinner: ({ size, strokeWidth }) => (
    <SvgRoot size={size} strokeWidth={strokeWidth}>
      <path d="M12 4a8 8 0 1 1-7.5 5.3" />
    </SvgRoot>
  ),
};
