import { useState } from 'react'
import { usePlanetXStore, IDENTITY_LABELS } from '../auth/planetxAuthStore'
import type { MissionId } from '../auth/planetxAuthStore'
import XPBar from '../../brand/components/XPBar'
import FleetPanel from '../../brand/components/FleetPanel'
import PlanetXIcon, { type PlanetXIconName } from '../../brand/ui/PlanetXIcon'

/**
 * 主中心屏幕 — XP条 + 任务Tab + 舰队Tab + 我的Tab
 */
export default function HubScreen() {
  const [tab, setTab] = useState<'missions' | 'team' | 'profile'>('missions')
  const {
    identity, level, xp, xpToNext, missionsCompleted,
    personalityType, setScreen, logout, teamSize, spreadCount,
  } = usePlanetXStore()

  const missions: {
    id: MissionId; icon: PlanetXIconName; name: string; reward: string; xp: number; requires?: MissionId
  }[] = [
    { id: 'personality', icon: 'crystal', name: '人格冷启动测评', reward: '+50 XP · 生成初始假设（将随行为更新）', xp: 50 },
    { id: 'team', icon: 'handshake', name: '组建3人舰队', reward: '+80 XP · 解锁隐藏星图', xp: 80, requires: 'personality' },
    { id: 'match', icon: 'target', name: '首次星际匹配', reward: '+40 XP · 获得匹配星图', xp: 40, requires: 'team' },
    { id: 'share', icon: 'signal', name: '发送星际信号', reward: '+30 XP · 邀请好友获得额外能量', xp: 30, requires: 'personality' },
  ]

  const allMissionsDone = (['personality', 'team', 'match', 'share'] as MissionId[]).every((id) =>
    missionsCompleted.includes(id),
  )

  const tabMeta: Record<typeof tab, { icon: PlanetXIconName; label: string }> = {
    missions: { icon: 'target', label: '任务' },
    team: { icon: 'fleet', label: '舰队' },
    profile: { icon: 'profile', label: '我的' },
  }

  const isMissionUnlocked = (m: typeof missions[number]) => {
    if (!m.requires) return true
    // Web+PWA 演示：舰队 ≥2 人即可开 match（与后端 API 一致）；team 任务 XP 仍要 3 人
    if (m.id === 'match') {
      return missionsCompleted.includes('team') || teamSize >= 2
    }
    return missionsCompleted.includes(m.requires)
  }

  const isMissionDone = (id: MissionId) => missionsCompleted.includes(id)

  return (
    <div>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '16px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 900, color: 'var(--px-color-accent)', letterSpacing: '2px', margin: 0 }}>
          Planet
          <span style={{ color: 'var(--px-color-purple-deep)', display: 'inline-block', animation: 'xSpin 8s linear infinite' }}>X</span>
        </h1>
        <p style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', letterSpacing: '0.2em', marginTop: '4px' }}>
          {identity ? IDENTITY_LABELS[identity] : ''}
        </p>
        <p
          style={{
            fontSize: '12px',
            color: 'var(--px-color-text-muted)',
            lineHeight: 1.65,
            margin: '10px auto 0',
            maxWidth: 320,
          }}
        >
          这里不是投简历的地方。先看清你在做什么、和谁共事过；画像会随着记录变准，机会是后面的事。
        </p>
      </div>

      {/* XP Bar */}
      <XPBar level={level} xp={xp} xpToNext={xpToNext} />

      {allMissionsDone && (
        <button
          type="button"
          onClick={() => setScreen('trust')}
          style={{
            width: '100%',
            marginBottom: 12,
            padding: '14px 14px',
            borderRadius: 12,
            border: '1px solid rgba(255,215,0,0.45)',
            background: 'linear-gradient(135deg, rgba(255,215,0,0.12), rgba(200,255,80,0.1))',
            color: '#FFD700',
            fontWeight: 800,
            fontSize: 13,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          通关大奖已解锁 · 打开信任档案
          <span style={{ display: 'block', fontSize: 11, fontWeight: 500, color: 'var(--px-color-text-muted)', marginTop: 4 }}>
            行为开始被看见 — 去查看声明，或继续在时间线沉淀
          </span>
        </button>
      )}

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button
          type="button"
          onClick={() => setScreen('timeline')}
          style={{
            flex: 1,
            padding: '12px 12px',
            borderRadius: 12,
            border: '1px solid rgba(200,255,80,0.3)',
            background: 'rgba(200,255,80,0.08)',
            color: 'var(--px-color-accent)',
            fontWeight: 700,
            fontSize: 12,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <PlanetXIcon name="timeline" size={16} color="currentColor" />
            时间线
          </span>
          <span style={{ display: 'block', fontSize: 10, fontWeight: 500, color: 'var(--px-color-text-muted)', marginTop: 4 }}>
            看见行为在长
          </span>
        </button>
        <button
          type="button"
          onClick={() => setScreen('trust')}
          style={{
            flex: 1,
            padding: '12px 12px',
            borderRadius: 12,
            border: '1px solid rgba(135,93,239,0.4)',
            background: 'rgba(135,93,239,0.12)',
            color: '#C4B5FD',
            fontWeight: 700,
            fontSize: 12,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <PlanetXIcon name="shield" size={16} color="currentColor" />
            信任档案
          </span>
          <span style={{ display: 'block', fontSize: 10, fontWeight: 500, color: 'var(--px-color-text-muted)', marginTop: 4 }}>
            凭证被看见
          </span>
        </button>
      </div>

      {/* Nav Tabs */}
      <div style={{ display: 'flex', gap: '4px', background: 'var(--px-color-bg-card)', borderRadius: '12px', padding: '4px', marginBottom: '16px' }}>
        {(['missions', 'team', 'profile'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              flex: 1,
              padding: '10px 0',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 600,
              border: 'none',
              background: tab === t ? 'rgba(200,255,80,0.1)' : 'transparent',
              color: tab === t ? 'var(--px-color-accent)' : 'var(--px-color-text-muted)',
              cursor: 'pointer',
              transition: 'all 0.2s',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            <PlanetXIcon name={tabMeta[t].icon} size={14} color="currentColor" />
            {tabMeta[t].label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'missions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {missions.map((m) => {
            const locked = !isMissionUnlocked(m)
            const done = isMissionDone(m.id)
            return (
              <button
                key={m.id}
                onClick={() => {
                  if (locked || done) return
                  if (m.id === 'personality') setScreen('quiz')
                  else if (m.id === 'match') setScreen('match')
                  else if (m.id === 'share') setScreen('result')
                }}
                disabled={locked}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '14px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'var(--px-color-bg-card)',
                  textAlign: 'left',
                  cursor: locked ? 'default' : 'pointer',
                  opacity: locked ? 0.4 : 1,
                  color: 'white',
                  width: '100%',
                }}
              >
                <span
                  style={{
                    width: 44,
                    height: 44,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    borderRadius: 12,
                    background: 'rgba(200,255,80,0.08)',
                    color: done ? 'var(--px-color-accent)' : 'var(--px-color-primary)',
                  }}
                >
                  <PlanetXIcon name={m.icon} size={22} color="currentColor" />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '14px', fontWeight: 'bold' }}>{m.name}</div>
                  <div style={{ fontSize: '12px', color: 'var(--px-color-accent)', marginTop: '2px' }}>{m.reward}</div>
                </div>
                <span
                  style={{
                    fontSize: '12px',
                    padding: '4px 10px',
                    borderRadius: '12px',
                    flexShrink: 0,
                    background: done ? 'rgba(200,255,80,0.15)' : 'rgba(255,255,255,0.05)',
                    color: done ? 'var(--px-color-accent)' : 'var(--px-color-text-muted)',
                  }}
                >
                  {done
                    ? '已完成'
                    : locked
                      ? m.id === 'match'
                        ? '需舰队≥2人'
                        : `需先完成${m.requires === 'personality' ? '人格测试' : '组队'}`
                      : '待完成'}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {tab === 'team' && <FleetPanel />}

      {tab === 'profile' && (
        <div>
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'center', color: 'var(--px-color-primary)' }}>
              {personalityType?.emoji
                ? <span style={{ fontSize: 48 }}>{personalityType.emoji}</span>
                : <PlanetXIcon name="planet" size={48} color="currentColor" />}
            </div>
            <div style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--px-color-accent)', marginTop: '8px' }}>
              {personalityType?.name ?? '未测试'}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--px-color-text-muted)' }}>
              {personalityType
                ? '初始假设 · 将随行为沉淀更新'
                : '完成人格冷启动测评，生成初始假设'}
            </div>
            {personalityType && (
              <div style={{ marginTop: 10, display: 'flex', gap: 10, justifyContent: 'center' }}>
                <button
                  type="button"
                  onClick={() => setScreen('timeline')}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 999,
                    border: '1px solid rgba(200,255,80,0.25)',
                    background: 'transparent',
                    color: 'var(--px-color-accent)',
                    fontSize: 12,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  查看时间线
                  <PlanetXIcon name="chevron-right" size={14} color="currentColor" />
                </button>
                <button
                  type="button"
                  onClick={() => setScreen('trust')}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 999,
                    border: '1px solid rgba(135,93,239,0.35)',
                    background: 'transparent',
                    color: '#C4B5FD',
                    fontSize: 12,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  信任档案
                  <PlanetXIcon name="chevron-right" size={14} color="currentColor" />
                </button>
              </div>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {[
              { v: missionsCompleted.length, l: '完成任务' },
              { v: teamSize, l: '舰队成员' },
              { v: spreadCount, l: '信号传播' },
              { v: xp, l: '总能量' },
            ].map((s, i) => (
              <div
                key={i}
                style={{
                  background: 'var(--px-color-bg-card)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  padding: '14px',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '24px', fontWeight: 900, color: 'var(--px-color-accent)' }}>{s.v}</div>
                <div style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', marginTop: '4px' }}>{s.l}</div>
              </div>
            ))}
          </div>
          <button
            onClick={logout}
            style={{
              width: '100%',
              marginTop: '16px',
              padding: '8px 0',
              borderRadius: '12px',
              fontSize: '12px',
              color: 'var(--px-color-text-muted)',
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'transparent',
              cursor: 'pointer',
              transition: 'all 0.2s',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            <PlanetXIcon name="logout" size={14} color="currentColor" />
            退出登录
          </button>
        </div>
      )}
    </div>
  )
}
