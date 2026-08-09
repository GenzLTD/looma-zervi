import PlanetXIcon, { type PlanetXIconName } from '../ui/PlanetXIcon'
import GlowCard from './GlowCard'

export interface StatItem {
  value: number | string
  label: string
  icon: PlanetXIconName
  color?: string
}

interface StatsPanelProps {
  stats: StatItem[]
  /** 每行列数，默认 2 */
  columns?: 2 | 3 | 4
}

/**
 * StatsPanel — 统计数字面板
 *
 * 2xN 或 3xN 网格布局，每格展示数值 + 标签 + 图标。
 * 数值使用品牌主色，标签使用三级文字色。
 */
export default function StatsPanel({ stats, columns = 2 }: StatsPanelProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gap: 8,
      }}
    >
      {stats.map((stat, i) => (
        <GlowCard
          key={i}
          padding="14px"
          glow="none"
          borderColor="var(--px-color-border-subtle)"
          hoverBorderColor="var(--px-color-border-default)"
        >
          <div style={{ textAlign: 'center' }}>
            <PlanetXIcon
              name={stat.icon}
              size={18}
              color={stat.color ?? 'var(--px-color-text-tertiary)'}
            />
            <div
              style={{
                fontSize: 'var(--lo-font-size-3xl)',
                fontWeight: 'var(--lo-font-black)',
                color: stat.color ?? 'var(--px-color-text-brand)',
                marginTop: 4,
              }}
            >
              {stat.value}
            </div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--px-color-text-tertiary)',
                marginTop: 2,
              }}
            >
              {stat.label}
            </div>
          </div>
        </GlowCard>
      ))}
    </div>
  )
}
