import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { createTimelineApi, type TimelineEvent, type TimelineGrowthResponse } from '@looma/shared-core'
import { getApiClient, usePlanetXStore } from '../auth/planetxAuthStore'

const KIND_LABEL: Record<string, string> = {
  initial_hypothesis: '起始画像',
  quiz_completed: '职业画像初测',
  project_record: '项目经历',
  check_in: '本周记录',
  share_authorized: '授权分享',
  match_scan: '匹配扫描',
  resume_ingest: '简历沉淀',
  interaction_log: '对话摘要',
  mission_completed: '任务完成',
  learning_activity: '学习行为',
}

const LEGACY_TITLE_REWRITE: Record<string, string> = {
  '初始假设（人格冷启动）': '起始画像',
  完成星际人格测评: '完成职业画像初测',
  完成人格冷启动测评: '完成职业画像初测',
  本周签到: '完成本周记录',
}

function kindLabel(kind: string) {
  return KIND_LABEL[kind] || kind
}

function formatOccurredAt(iso: string): string {
  const d = (iso || '').slice(0, 10)
  const m = d.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return d
  return `${Number(m[2])} 月 ${Number(m[3])} 日`
}

function payloadPersonality(ev: TimelineEvent): string {
  const raw = ev.payload?.personality_type
  return typeof raw === 'string' ? raw : ''
}

function displayTitle(ev: TimelineEvent): string {
  const personality = payloadPersonality(ev)
  if (ev.event_kind === 'initial_hypothesis') {
    return personality ? `当前方向：${personality}` : '完成职业画像初测'
  }
  if (ev.event_kind === 'quiz_completed') {
    return '完成职业画像初测'
  }
  if (ev.event_kind === 'check_in' && (!ev.title || ev.title === '本周签到')) {
    return '完成本周记录'
  }
  if (ev.title && LEGACY_TITLE_REWRITE[ev.title]) {
    return LEGACY_TITLE_REWRITE[ev.title]
  }
  return ev.title || kindLabel(ev.event_kind)
}

function displaySummary(ev: TimelineEvent): string {
  const personality = payloadPersonality(ev)
  if (ev.event_kind === 'initial_hypothesis') {
    return personality
      ? `当前方向：${personality}。这是起始画像，后续会根据实际经历持续调整。`
      : '这是起始画像，后续会根据实际经历持续调整。'
  }
  if (ev.event_kind === 'quiz_completed') {
    if (ev.summary && !ev.summary.startsWith('测评结果：')) return ev.summary
    if (ev.summary?.startsWith('测评结果：')) {
      return `当前方向：${ev.summary.slice('测评结果：'.length)}`
    }
    if (personality) return `当前方向：${personality}`
    return '你完成了职业画像初测。'
  }
  if (ev.event_kind === 'check_in' && (!ev.summary || ev.summary === '记录本周状态')) {
    return '记录了本周的行动与状态。'
  }
  return ev.summary
}

/**
 * 职业时间线 — 阅读顺序：我在哪 → 我能做什么 → 我积累了什么 → 过去发生了什么。
 */
export default function TimelineScreen() {
  const setScreen = usePlanetXStore((s) => s.setScreen)
  const setToast = usePlanetXStore((s) => s.setToast)
  const [items, setItems] = useState<TimelineEvent[]>([])
  const [growth, setGrowth] = useState<TimelineGrowthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [panel, setPanel] = useState<'none' | 'check_in' | 'project'>('none')
  const [mood, setMood] = useState('focused')
  const [focus, setFocus] = useState('')
  const [projectTitle, setProjectTitle] = useState('')
  const [projectSummary, setProjectSummary] = useState('')
  const [saving, setSaving] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const api = createTimelineApi(getApiClient())
      await api.backfill().catch(() => undefined)
      const [list, g] = await Promise.all([api.list({ limit: 50 }), api.growth()])
      setItems(list.items || [])
      setGrowth(g)
    } catch {
      setToast('时间线加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [setToast])

  useEffect(() => {
    reload()
  }, [reload])

  const submitCheckIn = async () => {
    setSaving(true)
    try {
      const api = createTimelineApi(getApiClient())
      await api.createEvent({
        event_kind: 'check_in',
        title: '完成本周记录',
        summary: focus || '记录了本周的行动与状态。',
        payload: { mood, focus: focus || null, blocker: null },
      })
      setPanel('none')
      setFocus('')
      setToast('已记录本周行动。这条记录会帮助职业画像继续完善。')
      await reload()
    } catch {
      setToast('记录失败')
    } finally {
      setSaving(false)
    }
  }

  const submitProject = async () => {
    if (!projectTitle.trim()) {
      setToast('请填写项目标题')
      return
    }
    setSaving(true)
    try {
      const api = createTimelineApi(getApiClient())
      await api.createEvent({
        event_kind: 'project_record',
        title: projectTitle.trim(),
        summary: projectSummary.trim(),
        payload: {
          role: '',
          outcome: projectSummary.trim(),
          raw_text_chars: projectSummary.trim().length,
        },
      })
      setPanel('none')
      setProjectTitle('')
      setProjectSummary('')
      setToast('项目已加入职业时间线，画像会据此调整。')
      await reload()
    } catch {
      setToast('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleExport = useCallback(async () => {
    setSaving(true)
    try {
      const api = createTimelineApi(getApiClient())
      const data = await api.exportMyData()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `planex-timeline-${data.user_id.slice(0, 8)}.json`
      a.click()
      URL.revokeObjectURL(url)
      setToast(`已导出 ${data.event_count} 条事件`)
    } catch {
      setToast('导出失败')
    } finally {
      setSaving(false)
    }
  }, [setToast])

  const handleDeleteAll = useCallback(async () => {
    setSaving(true)
    try {
      const api = createTimelineApi(getApiClient())
      const res = await api.deleteAllMyData()
      setToast(`已删除 ${res.deleted} 条事件`)
      setDeleteConfirm(false)
      setMoreOpen(false)
      await reload()
    } catch {
      setToast('删除失败')
    } finally {
      setSaving(false)
    }
  }, [setToast, reload])

  const handleDeleteEvent = useCallback(
    async (eventId: string) => {
      setSaving(true)
      try {
        const api = createTimelineApi(getApiClient())
        await api.deleteEvent(eventId)
        setToast('事件已删除')
        await reload()
      } catch {
        setToast('删除失败')
      } finally {
        setSaving(false)
      }
    },
    [setToast, reload],
  )

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
        <button
          type="button"
          onClick={() => setScreen('hub')}
          style={{
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.15)',
            color: 'var(--px-color-text-muted)',
            borderRadius: 10,
            padding: '6px 10px',
            cursor: 'pointer',
            marginTop: 2,
          }}
        >
          ← 返回
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--px-color-accent)' }}>职业时间线</div>
          <div style={{ fontSize: 12, color: 'var(--px-color-text-muted)', lineHeight: 1.55, marginTop: 4 }}>
            这里保存你的工作、学习、项目与探索经历，以及职业画像如何随记录变化。
          </div>
        </div>
        <button
          type="button"
          aria-label="更多操作"
          onClick={() => {
            setMoreOpen((v) => !v)
            setDeleteConfirm(false)
          }}
          style={{
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.12)',
            color: 'var(--px-color-text-muted)',
            borderRadius: 10,
            padding: '6px 10px',
            cursor: 'pointer',
            fontSize: 16,
            lineHeight: 1,
          }}
        >
          ···
        </button>
      </div>

      {moreOpen && (
        <div
          style={{
            background: 'var(--px-color-bg-card)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 12,
            padding: 10,
            marginBottom: 14,
          }}
        >
          <button type="button" onClick={handleExport} disabled={saving} style={moreItemStyle}>
            导出数据
          </button>
          {!deleteConfirm ? (
            <button type="button" onClick={() => setDeleteConfirm(true)} style={{ ...moreItemStyle, color: 'rgba(255,120,120,0.7)', fontWeight: 500 }}>
              清空时间线
            </button>
          ) : (
            <button type="button" onClick={handleDeleteAll} disabled={saving} style={{ ...moreItemStyle, color: '#f66' }}>
              {saving ? '删除中…' : '确认清空全部记录？此操作不可恢复'}
            </button>
          )}
        </div>
      )}

      {growth && (
        <div
          style={{
            background: 'var(--px-color-bg-card)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 12,
            padding: 14,
            marginBottom: 14,
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', marginBottom: 6, letterSpacing: 0.4 }}>
            当前状态
          </div>
          <div style={{ fontSize: 14, color: 'var(--px-color-text-bright)', lineHeight: 1.6, fontWeight: 600 }}>
            {growth.message}
          </div>
          {growth.hypothesis_present && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'rgba(200,255,80,0.75)', lineHeight: 1.55 }}>
              当前画像主要参考人格测评结果，仅作为起始判断。随着实际行动和项目记录增加，画像会持续调整。
            </div>
          )}
        </div>
      )}

      <div style={{ marginBottom: 8, fontSize: 11, color: 'var(--px-color-text-muted)', letterSpacing: 0.4 }}>
        接下来可以做什么
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => setPanel(panel === 'check_in' ? 'none' : 'check_in')}
          style={{ ...ctaCardStyle, outline: panel === 'check_in' ? '1px solid var(--px-color-accent)' : undefined }}
        >
          <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 6 }}>每周记录</div>
          <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', lineHeight: 1.5, fontWeight: 500 }}>
            记录这一周做了什么、关注什么，以及状态发生了哪些变化。
          </div>
        </button>
        <button
          type="button"
          onClick={() => setPanel(panel === 'project' ? 'none' : 'project')}
          style={{ ...ctaCardStyle, outline: panel === 'project' ? '1px solid var(--px-color-accent)' : undefined }}
        >
          <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 6 }}>记录项目</div>
          <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', lineHeight: 1.5, fontWeight: 500 }}>
            添加工作、学习、创作或个人项目，形成更完整的经历记录。
          </div>
        </button>
      </div>

      {panel === 'check_in' && (
        <div style={formCard}>
          <div style={{ fontSize: 13, marginBottom: 8, color: 'var(--px-color-text-muted)' }}>本周状态</div>
          <select
            value={mood}
            onChange={(e) => setMood(e.target.value)}
            style={inputStyle}
          >
            <option value="focused">专注</option>
            <option value="exploring">探索中</option>
            <option value="stressed">有压力</option>
            <option value="hopeful">有期待</option>
          </select>
          <input
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="本周做了什么、关注什么？（可选）"
            style={{ ...inputStyle, marginTop: 8 }}
          />
          <button type="button" disabled={saving} onClick={submitCheckIn} style={{ ...ctaStyle, width: '100%', marginTop: 10 }}>
            {saving ? '保存中…' : '完成本周记录'}
          </button>
        </div>
      )}

      {panel === 'project' && (
        <div style={formCard}>
          <input
            value={projectTitle}
            onChange={(e) => setProjectTitle(e.target.value)}
            placeholder="工作 / 学习 / 创作 / 个人项目名称"
            style={inputStyle}
          />
          <textarea
            value={projectSummary}
            onChange={(e) => setProjectSummary(e.target.value)}
            placeholder="你负责什么，目前处于什么阶段（可选）"
            rows={3}
            style={{ ...inputStyle, marginTop: 8, resize: 'vertical' }}
          />
          <button type="button" disabled={saving} onClick={submitProject} style={{ ...ctaStyle, width: '100%', marginTop: 10 }}>
            {saving ? '保存中…' : '加入职业时间线'}
          </button>
        </div>
      )}

      {growth && (
        <div
          style={{
            background: 'var(--px-color-bg-card)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 12,
            padding: 14,
            marginBottom: 14,
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', marginBottom: 10, letterSpacing: 0.4 }}>
            你已经积累了什么
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {growth.dimensions.map((d) => {
              const max = d.max ?? 5
              return (
                <div
                  key={d.id}
                  style={{
                    flex: '1 1 90px',
                    background: 'rgba(255,255,255,0.04)',
                    borderRadius: 10,
                    padding: '10px 8px',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--px-color-accent)' }}>
                    {d.level}
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--px-color-text-muted)' }}> / {max}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', marginTop: 2 }}>{d.label}</div>
                  {d.hint ? (
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 6, lineHeight: 1.4 }}>
                      {d.hint}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--px-color-text-muted)', padding: 32 }}>加载中…</div>
      ) : items.length === 0 ? (
        <div style={{ textAlign: 'center', color: 'var(--px-color-text-muted)', padding: '36px 12px' }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🌀</div>
          <div style={{ fontSize: 14, marginBottom: 6 }}>还没有职业记录</div>
          <div style={{ fontSize: 12, lineHeight: 1.6 }}>
            完成职业画像初测，或用上方「每周记录 / 记录项目」开始留下经历。
          </div>
        </div>
      ) : (
        <div>
          <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', marginBottom: 10, letterSpacing: 0.4 }}>
            过去发生了什么
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {items.map((ev) => {
              const summary = displaySummary(ev)
              return (
                <div
                  key={ev.id}
                  style={{
                    background: 'var(--px-color-bg-card)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 12,
                    padding: 12,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span
                      style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 999,
                        background:
                          ev.weight_role === 'hypothesis'
                            ? 'rgba(255,180,80,0.15)'
                            : 'rgba(200,255,80,0.12)',
                        color:
                          ev.weight_role === 'hypothesis'
                            ? 'rgba(255,200,120,0.95)'
                            : 'var(--px-color-accent)',
                      }}
                    >
                      {kindLabel(ev.event_kind)}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, color: 'var(--px-color-text-muted)' }}>
                        {formatOccurredAt(ev.occurred_at || '')}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteEvent(ev.id)}
                        disabled={saving}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'rgba(255,255,255,0.25)',
                          cursor: 'pointer',
                          fontSize: 14,
                          padding: '0 2px',
                          lineHeight: 1,
                        }}
                        title="删除此事件"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginTop: 8 }}>{displayTitle(ev)}</div>
                  {summary ? (
                    <div style={{ fontSize: 12, color: 'var(--px-color-text-muted)', marginTop: 4, lineHeight: 1.5 }}>
                      {summary}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

const ctaStyle: CSSProperties = {
  flex: 1,
  padding: '10px 0',
  borderRadius: 12,
  border: '1px solid rgba(200,255,80,0.35)',
  background: 'rgba(200,255,80,0.1)',
  color: 'var(--px-color-accent)',
  fontWeight: 700,
  fontSize: 13,
  cursor: 'pointer',
}

const ctaCardStyle: CSSProperties = {
  flex: '1 1 150px',
  padding: '12px 12px 14px',
  borderRadius: 12,
  border: '1px solid rgba(200,255,80,0.35)',
  background: 'rgba(200,255,80,0.1)',
  color: 'var(--px-color-accent)',
  fontWeight: 700,
  fontSize: 13,
  cursor: 'pointer',
  textAlign: 'left',
}

const moreItemStyle: CSSProperties = {
  display: 'block',
  width: '100%',
  background: 'transparent',
  border: 'none',
  color: 'var(--px-color-text-muted)',
  textAlign: 'left',
  padding: '8px 6px',
  fontSize: 13,
  cursor: 'pointer',
  fontWeight: 600,
}

const formCard: CSSProperties = {
  background: 'var(--px-color-bg-card)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 12,
  padding: 12,
  marginBottom: 14,
}

const inputStyle: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  background: 'rgba(0,0,0,0.25)',
  border: '1px solid rgba(255,255,255,0.12)',
  borderRadius: 10,
  padding: '10px 12px',
  color: 'var(--px-color-text-bright)',
  fontSize: 13,
}
