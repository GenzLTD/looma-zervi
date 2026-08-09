import type { ReactNode, CSSProperties } from 'react'

/**
 * GlowCard — 深空发光卡片容器
 *
 * 三层发光系统：
 *   1. 外发光 — CSS 变量（默认 --px-shadow-glow，可覆盖）
 *   2. 边框渐变 — 半透明品牌色边框
 *   3. Hover 时 border-color 加亮 + 微提亮
 *
 * 通过 --px-* Token 与 PlanetX 主题联动，也可通过 props 覆盖用于 TSpace 等其他品牌。
 */
export interface GlowCardProps {
  children: ReactNode
  /** 外发光阴影，默认 var(--px-shadow-glow) */
  glow?: string
  /** 边框颜色，默认 var(--px-color-border-subtle) */
  borderColor?: string
  /** Hover 边框颜色，默认 var(--px-color-border-default) */
  hoverBorderColor?: string
  /** 背景色，默认 var(--px-card-bg) */
  background?: string
  /** 圆角，默认 var(--lo-radius-lg) */
  borderRadius?: string
  /** 内边距，默认 20px */
  padding?: string
  /** 是否禁用 hover 效果 */
  noHover?: boolean
  /** 可点击时的 cursor */
  clickable?: boolean
  style?: CSSProperties
  className?: string
  onClick?: () => void
}

export default function GlowCard({
  children,
  glow = 'var(--px-shadow-glow)',
  borderColor = 'var(--px-color-border-subtle)',
  hoverBorderColor = 'var(--px-color-border-default)',
  background = 'var(--px-card-bg)',
  borderRadius = 'var(--lo-radius-lg)',
  padding = '20px',
  noHover = false,
  clickable,
  style,
  className,
  onClick,
}: GlowCardProps) {
  return (
    <div
      className={className}
      onClick={onClick}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter') onClick() } : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      style={{
        width: '100%',
        boxSizing: 'border-box',
        background,
        border: `1px solid ${borderColor}`,
        borderRadius,
        boxShadow: glow,
        padding,
        cursor: clickable || onClick ? 'pointer' : undefined,
        transition: noHover ? undefined : 'all var(--lo-anim-fast)',
        ...style,
      }}
      onMouseEnter={noHover ? undefined : (e) => {
        e.currentTarget.style.borderColor = hoverBorderColor
        e.currentTarget.style.boxShadow = `0 0 24px rgba(108,99,255,0.18), ${glow}`
      }}
      onMouseLeave={noHover ? undefined : (e) => {
        e.currentTarget.style.borderColor = borderColor
        e.currentTarget.style.boxShadow = glow
      }}
    >
      {children}
    </div>
  )
}
