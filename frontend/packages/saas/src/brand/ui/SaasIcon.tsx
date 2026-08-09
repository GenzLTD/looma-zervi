/**
 * SaasIcon — SVG icon component for TSpace
 *
 * Mirrors PlanetXIcon API but styled for TSpace brand tokens.
 * All colors use currentColor → inherit from parent via CSS var.
 */
import type { ReactNode } from 'react'

// ================================================================
// Icon glyphs (inline SVG, 20×20 viewBox)
// ================================================================
function SvgWrapper({ children, size = 20, strokeWidth = 1.75 }: {
  children: ReactNode
  size: number
  strokeWidth: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  )
}

// prettier-ignore
const GLYPHS = {
  // ── Core nav (P0) ──
  dashboard:        ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><rect x="2" y="2" width="7" height="7" rx="1"/><rect x="11" y="2" width="7" height="7" rx="1"/><rect x="2" y="11" width="7" height="7" rx="1"/><rect x="11" y="11" width="7" height="7" rx="1"/></SvgWrapper>,
  candidates:       ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="7" cy="5" r="2"/><path d="M3 14v-1a4 4 0 0 1 4-4h0a4 4 0 0 1 4 4v1"/><circle cx="15" cy="7" r="2"/><path d="M12 16v-1a4 4 0 0 1 2-3.46"/></SvgWrapper>,
  jobs:             ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M2 5h16v11a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5z"/><path d="M7 5V3a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/></SvgWrapper>,
  query:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="9" cy="9" r="5"/><path d="M13 13l5 5"/></SvgWrapper>,
  resume:           ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M4 2h8l4 4v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><path d="M12 2v4h4"/><path d="M6 9h8"/><path d="M6 12h8"/><path d="M6 15h4"/></SvgWrapper>,
  match:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="6" cy="6" r="3"/><circle cx="14" cy="14" r="3"/><path d="M14 6l-4 8"/></SvgWrapper>,
  report:           ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M3 17V3h10l4 4v10a2 2 0 0 1-2 2H5a2 2 0 0 0 2-2"/><path d="M13 3v4h4"/><path d="M7 9h4"/><path d="M7 13h6"/></SvgWrapper>,
  settings:         ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="10" cy="10" r="2.5"/><path d="M10 2v2"/><path d="M10 16v2"/><path d="M2 10h2"/><path d="M16 10h2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M13.66 13.66l1.41 1.41"/><path d="M4.93 15.07l1.41-1.41"/><path d="M13.66 6.34l1.41-1.41"/></SvgWrapper>,

  // ── Feature cards (P1) ──
  robot:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><rect x="4" y="6" width="12" height="10" rx="2"/><path d="M7 3h6"/><circle cx="8" cy="10" r="0.5" fill="currentColor" stroke="none"/><circle cx="12" cy="10" r="0.5" fill="currentColor" stroke="none"/><path d="M8 13.5c.67.5 1.33.5 2 .5s1.33 0 2-.5"/></SvgWrapper>,
  chart:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M3 17V7h4"/><path d="M8 17V4h4"/><path d="M13 17v-6h4"/></SvgWrapper>,

  // ── Actions (P1) ──
  timer:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/><path d="M10 2v1"/></SvgWrapper>,
  download:         ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M2 14v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/><path d="M7 8l3 3 3-3"/><path d="M10 11V2"/></SvgWrapper>,
  upload:           ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M2 14v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/><path d="M7 8l3-3 3 3"/><path d="M10 5v9"/></SvgWrapper>,
  filter:           ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><polygon points="3,3 9,10 9,15 11,17 11,10 17,3"/></SvgWrapper>,
  check:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M4 10l4 4 8-8"/></SvgWrapper>,
  cross:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M4 4l12 12"/><path d="M16 4l-12 12"/></SvgWrapper>,
  warning:          ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M10 3L3 17h14L10 3z"/><path d="M10 11v2"/><circle cx="10" cy="14.5" r="0.5" fill="currentColor" stroke="none"/></SvgWrapper>,
  info:             ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="10" cy="10" r="7"/><path d="M10 9v5"/><circle cx="10" cy="6.5" r="0.5" fill="currentColor" stroke="none"/></SvgWrapper>,
  trendUp:          ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M2 14l5-5 3 3 8-8"/><path d="M14 4h4v4"/></SvgWrapper>,
  trendDown:        ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M2 4l5 5 3-3 8 8"/><path d="M14 14h4v-4"/></SvgWrapper>,
  pipeline:         ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M2 5h4l2 4h8l2 4H2"/><path d="M6 5v10"/></SvgWrapper>,
  radar:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="4"/><circle cx="10" cy="10" r="1"/><path d="M10 2v16"/></SvgWrapper>,
  compare:          ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><rect x="1" y="3" width="7" height="14" rx="1"/><rect x="12" y="7" width="7" height="10" rx="1"/></SvgWrapper>,
  time:             ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="10" cy="10" r="7"/><path d="M10 6v4l2.5 2"/></SvgWrapper>,

  // ── P2: Navigation expansion ──
  trust:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M10 2L3 5v4c0 4.5 3 8.7 7 9.9 4-1.2 7-5.4 7-9.9V5l-7-3z"/></SvgWrapper>,
  poetry:           ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M4 3h12a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M6 7h5"/><path d="M6 10h8"/><path d="M6 13h6"/><path d="M6 16h3"/></SvgWrapper>,
  challenge:        ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M10 3l1.5 4.5L16 8l-3.5 2L13.5 15 10 12.5 6.5 15 7.5 10 4 8l4.5-.5L10 3z"/></SvgWrapper>,
  consent:          ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><rect x="3" y="5" width="14" height="12" rx="2"/><path d="M7 10l2 2 4-4"/></SvgWrapper>,
  logout:           ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M6 4h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6"/><path d="M2 10h10"/><path d="M9 7l3 3-3 3"/></SvgWrapper>,
  lock:             ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><rect x="4" y="8" width="12" height="9" rx="1"/><path d="M7 8V5a3 3 0 0 1 6 0v3"/></SvgWrapper>,
  pricing:          ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M10 2l3 8H7l3-8z"/><path d="M5 14l2 4h6l2-4"/></SvgWrapper>,
  chat:             ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M3 11V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9l-4 3v-3H5a2 2 0 0 1-2-2z"/></SvgWrapper>,
  admin:            ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><circle cx="10" cy="7" r="2.5"/><path d="M5 16v-1a5 5 0 0 1 5-5h0a5 5 0 0 1 5 5v1"/><path d="M16 5l2 2-2 2"/><path d="M18 7h-4"/></SvgWrapper>,
  trophy:           ({ s, sw }: { s: number; sw: number }) => <SvgWrapper size={s} strokeWidth={sw}><path d="M5 3h10v2a4 4 0 0 1-4 4h-2a4 4 0 0 1-4-4V3z"/><path d="M6 9v2a4 4 0 0 0 8 0V9"/><path d="M10 13v4"/><path d="M8 17h4"/></SvgWrapper>,
} as const

export type SaasIconName = keyof typeof GLYPHS

export interface SaasIconProps {
  name: SaasIconName
  size?: number
  color?: string
  strokeWidth?: number
  title?: string
  className?: string
  style?: React.CSSProperties
}

export default function SaasIcon({
  name,
  size = 20,
  color = 'currentColor',
  strokeWidth = 1.75,
  title,
  className,
  style,
}: SaasIconProps) {
  const glyph = GLYPHS[name]
  return (
    <span
      className={className}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        color,
        lineHeight: 0,
        ...style,
      }}
    >
      {glyph({ s: size, sw: strokeWidth })}
    </span>
  )
}
