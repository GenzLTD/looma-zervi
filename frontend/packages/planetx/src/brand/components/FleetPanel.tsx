import { useState } from 'react'
import GlowCard from './GlowCard'

export interface FleetMember {
  id: string
  name: string
  avatarLabel?: string
  role?: string
  matchScore?: number
  joinedAt?: string
}

export interface FleetData {
  id: string
  name: string
  code: string       // 舰队加入码（fleets.invite_code，非候选人/信任码）
  members: FleetMember[]
  maxMembers: number
  totalMatches: number
  weeklyActivity: number
  createdAt: string
}

type FleetView = 'empty' | 'creating' | 'active' | 'memberDetail'

interface FleetPanelProps {
  fleet?: FleetData
  onCreate?: (name: string) => void
  onJoin?: (code: string) => void
  onInvite?: () => void
  onLeave?: () => void
  loading?: boolean
}

/**
 * FleetPanel — 舰队管理面板（多屏版本）
 *
 * 四屏状态：
 *   1. empty — 未加入舰队，展示创建/加入入口
 *   2. creating — 创建舰队表单
 *   3. active — 舰队详情（成员列表、数据、邀请）
 *   4. memberDetail — 选中某个成员的详细信息（可扩展）
 *
 * 全部 CSS 值使用 var(--px-*) Token，对接 PlanetX 主题。
 */
export default function FleetPanel({
  fleet,
  onCreate,
  onJoin,
  onInvite,
  onLeave,
  loading = false,
}: FleetPanelProps) {
  const [view, setView] = useState<FleetView>(fleet ? 'active' : 'empty')
  const [fleetName, setFleetName] = useState('')
  const [joinCode, setJoinCode] = useState('')
  const [copied, setCopied] = useState(false)

  const handleCopyCode = async () => {
    if (!fleet?.code) return
    try {
      await navigator.clipboard.writeText(fleet.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback
    }
  }

  // ========== EMPTY ==========
  if (!fleet && view === 'empty') {
    return (
      <GlowCard
        padding="28px 20px"
        glow="none"
        borderColor="var(--px-color-border-subtle)"
      >
        <div style={{ textAlign: 'center' }}>
          {/* Placeholder illustration */}
          <div style={{
            width: 80,
            height: 80,
            margin: '0 auto 16px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, rgba(108,99,255,0.12), rgba(0,212,255,0.08))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 36,
          }}>
            🛸
          </div>

          <h3 style={{
            margin: 0,
            fontSize: 'var(--lo-font-size-lg)',
            fontWeight: 700,
            color: 'var(--px-color-text-primary)',
          }}>
            加入舰队
          </h3>
          <p style={{
            margin: '8px 0 20px',
            fontSize: 13,
            color: 'var(--px-color-text-tertiary)',
            lineHeight: 1.6,
          }}>
            创建或加入舰队，与队友共创星际传奇。
            <br />
            舰队成员共享匹配数据与活动进度。
          </p>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button
              type="button"
              onClick={() => setView('creating')}
              style={{
                padding: '10px 24px',
                fontSize: 14,
                fontWeight: 700,
                border: 'none',
                borderRadius: 'var(--lo-radius-full)',
                background: 'var(--px-gradient-primary)',
                color: '#fff',
                cursor: 'pointer',
              }}
            >
              🚀 创建舰队
            </button>
            <button
              type="button"
              disabled={loading}
              style={{
                padding: '10px 24px',
                fontSize: 14,
                fontWeight: 600,
                border: '1px solid var(--px-color-border-default)',
                borderRadius: 'var(--lo-radius-full)',
                background: 'transparent',
                color: 'var(--px-color-text-secondary)',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              🔗 加入舰队
            </button>
          </div>
        </div>
      </GlowCard>
    )
  }

  // ========== CREATING ==========
  if (view === 'creating') {
    return (
      <GlowCard padding="24px 20px">
        <h3 style={{
          margin: '0 0 16px',
          fontSize: 'var(--lo-font-size-lg)',
          fontWeight: 700,
          color: 'var(--px-color-text-primary)',
        }}>
          🚀 创建舰队
        </h3>

        <label
          style={{
            display: 'block',
            fontSize: 12,
            color: 'var(--px-color-text-secondary)',
            marginBottom: 6,
            fontWeight: 600,
          }}
        >
          舰队名称
        </label>
        <input
          type="text"
          placeholder="给你的舰队起个酷名字..."
          value={fleetName}
          onChange={(e) => setFleetName(e.target.value)}
          maxLength={20}
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '10px 14px',
            fontSize: 14,
            background: 'var(--px-color-surface-root)',
            border: '1px solid var(--px-color-border-subtle)',
            borderRadius: 'var(--lo-radius-md)',
            color: 'var(--px-color-text-primary)',
            outline: 'none',
            marginBottom: 16,
          }}
        />

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            type="button"
            onClick={() => onCreate?.(fleetName)}
            disabled={!fleetName.trim() || loading}
            style={{
              flex: 1,
              padding: '10px 0',
              fontSize: 14,
              fontWeight: 700,
              border: 'none',
              borderRadius: 'var(--lo-radius-full)',
              background: fleetName.trim() ? 'var(--px-gradient-primary)' : 'var(--px-color-border-subtle)',
              color: fleetName.trim() ? '#fff' : 'var(--px-color-text-tertiary)',
              cursor: fleetName.trim() ? 'pointer' : 'not-allowed',
            }}
          >
            确认创建
          </button>
          <button
            type="button"
            onClick={() => setView('empty')}
            style={{
              padding: '10px 20px',
              fontSize: 14,
              fontWeight: 600,
              border: '1px solid var(--px-color-border-default)',
              borderRadius: 'var(--lo-radius-full)',
              background: 'transparent',
              color: 'var(--px-color-text-secondary)',
              cursor: 'pointer',
            }}
          >
            返回
          </button>
        </div>
      </GlowCard>
    )
  }

  // ========== ACTIVE ==========
  if (!fleet) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Fleet Header */}
      <GlowCard
        padding="18px 20px"
        borderColor="var(--px-color-brand)"
        glow="var(--px-ship-glow)"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 24 }}>🛸</span>
            <div>
              <div style={{ fontSize: 'var(--lo-font-size-base)', fontWeight: 700, color: 'var(--px-color-text-primary)' }}>
                {fleet.name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--px-color-text-tertiary)', marginTop: 2 }}>
                创建于 {fleet.createdAt}
              </div>
            </div>
          </div>

          {/* Fleet join code */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <code style={{
              padding: '4px 10px',
              fontSize: 12,
              fontWeight: 700,
              background: 'rgba(108,99,255,0.1)',
              borderRadius: 'var(--lo-radius-sm)',
              color: 'var(--px-color-brand)',
              letterSpacing: 0.5,
            }}>
              {fleet.code}
            </code>
            <button
              type="button"
              onClick={handleCopyCode}
              style={{
                padding: '4px 12px',
                fontSize: 11,
                fontWeight: 600,
                border: '1px solid var(--px-color-border-default)',
                borderRadius: 'var(--lo-radius-sm)',
                background: 'transparent',
                color: 'var(--px-color-text-secondary)',
                cursor: 'pointer',
              }}
            >
              {copied ? '✓ 已复制' : '复制'}
            </button>
          </div>
        </div>
      </GlowCard>

      {/* Fleet Stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 8,
      }}>
        {[
          { value: fleet.members.length, label: '成员', icon: '👥' },
          { value: fleet.maxMembers, label: '上限', icon: '⬆️' },
          { value: fleet.totalMatches, label: '总匹配', icon: '⭐' },
        ].map((stat) => (
          <GlowCard
            key={stat.label}
            padding="12px"
            glow="none"
            borderColor="var(--px-color-border-subtle)"
            hoverBorderColor="var(--px-color-border-default)"
          >
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: 18 }}>{stat.icon}</span>
              <div style={{
                fontSize: 'var(--lo-font-size-2xl)',
                fontWeight: 800,
                color: 'var(--px-color-text-brand)',
                marginTop: 2,
              }}>
                {stat.value}
              </div>
              <div style={{
                fontSize: 11,
                color: 'var(--px-color-text-tertiary)',
                marginTop: 1,
              }}>
                {stat.label}
              </div>
            </div>
          </GlowCard>
        ))}

        {/* Weekly activity — spans full width */}
        <div style={{ gridColumn: '1 / -1' }}>
          <GlowCard
            padding="12px 14px"
            glow="none"
            borderColor="var(--px-color-border-subtle)"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: 12, color: 'var(--px-color-text-secondary)' }}>
                📊 本周活跃度
              </div>
              <div style={{
                fontSize: 'var(--lo-font-size-xl)',
                fontWeight: 700,
                color: 'var(--px-color-text-brand)',
              }}>
                {fleet.weeklyActivity}%
              </div>
            </div>
            <div style={{
              height: 4,
              background: 'var(--px-color-surface-root)',
              borderRadius: 'var(--lo-radius-full)',
              marginTop: 8,
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: `${fleet.weeklyActivity}%`,
                background: 'var(--px-gradient-primary)',
                borderRadius: 'var(--lo-radius-full)',
                transition: 'width 0.6s ease',
              }} />
            </div>
          </GlowCard>
        </div>
      </div>

      {/* Members */}
      <div>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 8,
        }}>
          <span style={{
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--px-color-text-secondary)',
          }}>
            👥 舰队成员 ({fleet.members.length}/{fleet.maxMembers})
          </span>
          {onInvite && (
            <button
              type="button"
              onClick={onInvite}
              style={{
                padding: '4px 14px',
                fontSize: 11,
                fontWeight: 600,
                border: '1px solid var(--px-color-border-default)',
                borderRadius: 'var(--lo-radius-full)',
                background: 'transparent',
                color: 'var(--px-color-text-brand)',
                cursor: 'pointer',
              }}
            >
              + 邀请队友
            </button>
          )}
        </div>

        {fleet.members.length === 0 ? (
          <GlowCard padding="24px" glow="none" borderColor="var(--px-color-border-subtle)">
            <div style={{ textAlign: 'center', color: 'var(--px-color-text-tertiary)', fontSize: 13 }}>
              暂无成员，快去邀请队友吧！
            </div>
          </GlowCard>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {fleet.members.map((member) => (
              <GlowCard
                key={member.id}
                padding="12px 14px"
                glow="none"
                borderColor="var(--px-color-border-subtle)"
                hoverBorderColor="var(--px-color-border-default)"
                clickable
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, var(--px-color-brand), rgba(0,212,255,0.6))',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: 14,
                    flexShrink: 0,
                  }}>
                    {member.avatarLabel ?? member.name.charAt(0)}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--px-color-text-primary)' }}>
                      {member.name}
                    </div>
                    {member.role && (
                      <div style={{ fontSize: 11, color: 'var(--px-color-text-tertiary)' }}>
                        {member.role}
                      </div>
                    )}
                  </div>

                  {member.matchScore !== undefined && (
                    <div style={{
                      padding: '2px 8px',
                      borderRadius: 'var(--lo-radius-full)',
                      background: 'rgba(16,185,129,0.1)',
                      color: 'var(--px-color-success)',
                      fontSize: 12,
                      fontWeight: 700,
                    }}>
                      {member.matchScore}%
                    </div>
                  )}
                </div>
              </GlowCard>
            ))}
          </div>
        )}
      </div>

      {/* Leave button */}
      {onLeave && (
        <button
          type="button"
          onClick={onLeave}
          style={{
            width: '100%',
            padding: '10px 0',
            fontSize: 12,
            fontWeight: 600,
            border: '1px solid var(--px-color-danger)',
            borderRadius: 'var(--lo-radius-md)',
            background: 'transparent',
            color: 'var(--px-color-danger)',
            cursor: 'pointer',
            opacity: 0.6,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
          onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.6' }}
        >
          离开舰队
        </button>
      )}
    </div>
  )
}
