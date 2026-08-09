import { useMemo } from 'react'

export interface RadarDimension {
  key: string
  label: string
  score: number   // 0–100
  fullScore?: number
  color?: string
}

interface CandidateRadarChartProps {
  dimensions: RadarDimension[]
  size?: number
  candidateName?: string
}

const DEFAULT_COLORS = [
  'var(--tsp-chart-blue)',
  'var(--tsp-chart-purple)',
  'var(--tsp-chart-green)',
  'var(--tsp-chart-orange)',
  'var(--tsp-chart-red)',
  'var(--tsp-chart-teal)',
]

/**
 * CandidateRadarChart — SVG 雷达图
 *
 * 多维度能力可视化：
 *   - 六边形底图（3 层刻度环）
 *   - 维度轴线 + 标签（自动旋转）
 *   - 填充区域（半透明） + 描边
 *   - 数值圆点
 *
 * Token 对齐：使用 var(--tsp-*) 系列。
 */
export default function CandidateRadarChart({
  dimensions,
  size = 240,
  candidateName,
}: CandidateRadarChartProps) {
  const cx = size / 2
  const cy = size / 2
  const radius = size * 0.34
  const levels = 3

  const points = useMemo(() => {
    const n = dimensions.length
    if (n < 3) return { axes: [], dataPoints: '' }

    return {
      axes: Array.from({ length: n }, (_, i) => {
        const angle = (2 * Math.PI * i) / n - Math.PI / 2
        return { angle, x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }
      }),
      dataPoints: Array.from({ length: n }, (_, i) => {
        const angle = (2 * Math.PI * i) / n - Math.PI / 2
        const r = radius * (dimensions[i].score / 100)
        return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
      }).join(' '),
    }
  }, [dimensions, cx, cy, radius])

  if (dimensions.length < 3) {
    return (
      <div style={{ padding: 20, textAlign: 'center', color: 'var(--tsp-color-text-tertiary)', fontSize: 13 }}>
        需要至少 3 个维度才能展示雷达图
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 12,
      }}
    >
      {candidateName && (
        <div style={{ fontSize: 'var(--lo-font-size-sm)', fontWeight: 700, color: 'var(--tsp-color-text-primary)' }}>
          {candidateName}
        </div>
      )}

      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={candidateName ? `${candidateName} 能力雷达图` : '能力雷达图'}
      >
        {/* Level rings */}
        {Array.from({ length: levels }, (_, lvl) => {
          const r = (radius / levels) * (lvl + 1)
          return (
            <polygon
              key={`ring-${lvl}`}
              points={points.axes
                .map((a) => `${cx + r * Math.cos(a.angle)},${cy + r * Math.sin(a.angle)}`)
                .join(' ')}
              fill="none"
              stroke="var(--tsp-color-border-subtle)"
              strokeWidth={0.5}
            />
          )
        })}

        {/* Axis lines */}
        {points.axes.map((a, i) => (
          <line
            key={`axis-${i}`}
            x1={cx}
            y1={cy}
            x2={a.x}
            y2={a.y}
            stroke="var(--tsp-color-border-subtle)"
            strokeWidth={0.5}
          />
        ))}

        {/* Data polygon */}
        <polygon
          points={points.dataPoints}
          fill="var(--tsp-radar-fill, rgba(37, 99, 235, 0.15))"
          stroke="var(--tsp-radar-stroke, rgba(37, 99, 235, 0.6))"
          strokeWidth={1.5}
        />

        {/* Data dots */}
        {dimensions.map((d, i) => {
          const angle = (2 * Math.PI * i) / dimensions.length - Math.PI / 2
          const r = radius * (d.score / 100)
          const x = cx + r * Math.cos(angle)
          const y = cy + r * Math.sin(angle)
          return (
            <circle
              key={`dot-${i}`}
              cx={x}
              cy={y}
              r={3}
              fill={d.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
              stroke="white"
              strokeWidth={1}
            />
          )
        })}

        {/* Axis labels */}
        {dimensions.map((d, i) => {
          const angle = (2 * Math.PI * i) / dimensions.length - Math.PI / 2
          const labelR = radius + 20
          const x = cx + labelR * Math.cos(angle)
          const y = cy + labelR * Math.sin(angle)
          return (
            <text
              key={`label-${i}`}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="var(--tsp-color-text-secondary)"
              fontSize={10}
              fontWeight={600}
            >
              {d.label}
            </text>
          )
        })}

        {/* Score labels inside dots */}
        {dimensions.map((d, i) => {
          const angle = (2 * Math.PI * i) / dimensions.length - Math.PI / 2
          const r = radius * (d.score / 100) - 10
          const x = cx + r * Math.cos(angle)
          const y = cy + r * Math.sin(angle)
          return (
            <text
              key={`score-${i}`}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              fill={d.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
              fontSize={9}
              fontWeight={700}
            >
              {d.score}
            </text>
          )
        })}
      </svg>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
        {dimensions.map((d, i) => (
          <div key={d.key} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: d.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length],
                flexShrink: 0,
              }}
            />
            <span style={{ color: 'var(--tsp-color-text-secondary)' }}>{d.label}</span>
            <span style={{ color: 'var(--tsp-color-text-primary)', fontWeight: 600 }}>{d.score}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
