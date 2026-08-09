import CandidateRadarChart, { type RadarDimension } from './CandidateRadarChart'

export interface CandidateDetail {
  id: string
  name: string
  role: string
  matchScore: number
  stage: 'new' | 'review' | 'interview' | 'offer' | 'rejected'
  dimensions: RadarDimension[]
  tags: string[]
  avatarLabel?: string
  summary?: string
}

interface CandidateDetailCardProps {
  candidate: CandidateDetail
  onAction?: (action: 'view' | 'schedule' | 'compare', candidate: CandidateDetail) => void
  collapsed?: boolean
}

const STAGE_LABELS: Record<CandidateDetail['stage'], { label: string; color: string }> = {
  new: { label: '新入库', color: 'var(--tsp-pipeline-new)' },
  review: { label: 'AI 初筛', color: 'var(--tsp-pipeline-review)' },
  interview: { label: '面试中', color: 'var(--tsp-pipeline-interview)' },
  offer: { label: 'Offer', color: 'var(--tsp-pipeline-offer)' },
  rejected: { label: '已归档', color: 'var(--tsp-pipeline-rejected)' },
}

/**
 * CandidateDetailCard — 候选人详细信息卡片
 *
 * 功能区块：
 *   - 头像 + 姓名 + 匹配度 + 当前阶段标签
 *   - 多维度雷达图
 *   - 技能标签列表
 *   - 候选人摘要
 *   - 操作按钮（查看/面试/对比）
 */
export default function CandidateDetailCard({ candidate, onAction, collapsed = false }: CandidateDetailCardProps) {
  const stage = STAGE_LABELS[candidate.stage]
  const initial = candidate.avatarLabel ?? candidate.name.charAt(0)

  return (
    <div
      style={{
        background: 'var(--tsp-color-surface-card)',
        border: '1px solid var(--tsp-color-border-subtle)',
        borderRadius: 'var(--lo-radius-lg)',
        overflow: 'hidden',
        transition: 'all var(--lo-anim-fast)',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '20px 20px 0',
      }}>
        {/* Avatar */}
        <div style={{
          width: 48,
          height: 48,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--tsp-brand-primary), var(--tsp-chart-purple))',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 800,
          fontSize: 18,
          flexShrink: 0,
        }}>
          {initial}
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 'var(--lo-font-size-base)', fontWeight: 700, color: 'var(--tsp-color-text-primary)' }}>
              {candidate.name}
            </span>
            <span style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 'var(--lo-radius-full)',
              background: `${stage.color}20`,
              color: stage.color,
              fontWeight: 600,
              flexShrink: 0,
            }}>
              {stage.label}
            </span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--tsp-color-text-secondary)' }}>
            {candidate.role}
          </div>
        </div>

        {/* Match Score */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div style={{
            width: 52,
            height: 52,
            borderRadius: '50%',
            border: '2px solid var(--tsp-chart-green)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(16,185,129,0.06)',
          }}>
            <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--tsp-chart-green)' }}>
              {candidate.matchScore}
            </span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--tsp-color-text-tertiary)', marginTop: 2 }}>
            匹配度
          </div>
        </div>
      </div>

      {/* Radar Chart */}
      {!collapsed && (
        <div style={{ padding: '12px 20px', display: 'flex', justifyContent: 'center' }}>
          <CandidateRadarChart
            dimensions={candidate.dimensions}
            size={220}
          />
        </div>
      )}

      {/* Summary */}
      {!collapsed && candidate.summary && (
        <div style={{
          padding: '0 20px 14px',
          fontSize: 12,
          color: 'var(--tsp-color-text-secondary)',
          lineHeight: 1.6,
        }}>
          {candidate.summary}
        </div>
      )}

      {/* Tags */}
      {!collapsed && candidate.tags.length > 0 && (
        <div style={{ padding: '0 20px 14px', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {candidate.tags.map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: 11,
                padding: '3px 10px',
                borderRadius: 'var(--lo-radius-sm)',
                background: 'var(--tsp-color-surface-root)',
                color: 'var(--tsp-color-text-secondary)',
                border: '1px solid var(--tsp-color-border-subtle)',
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      {onAction && (
        <div style={{
          display: 'flex',
          borderTop: '1px solid var(--tsp-color-border-subtle)',
        }}>
          {(['view', 'schedule', 'compare'] as const).map((action) => (
            <button
              key={action}
              type="button"
              onClick={() => onAction(action, candidate)}
              style={{
                flex: 1,
                padding: '10px 0',
                fontSize: 12,
                fontWeight: 600,
                border: 'none',
                background: 'transparent',
                color: 'var(--tsp-brand-primary)',
                cursor: 'pointer',
                transition: 'background var(--lo-anim-fast)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(37,99,235,0.05)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              {action === 'view' && '查看详情'}
              {action === 'schedule' && '安排面试'}
              {action === 'compare' && '对比分析'}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
