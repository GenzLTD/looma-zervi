import { useEffect, useRef, useState } from 'react'
import {
  createGameApi,
  deriveMatchUiState,
  getShareText,
  type FleetMatchResponse,
  type MatchConsensusItem,
} from '@looma/shared-core'
import { usePlanetXStore, getApiClient } from '../auth/planetxAuthStore'

type Phase = 'scanning' | 'result' | 'error'

/**
 * 首次星际匹配 — 舰队内人格互补 + 阶段二共识三分流 UI
 */
export default function MatchScreen() {
  const {
    setScreen,
    completeMission,
    missionsCompleted,
    setAchievement,
    setToast,
    personalityType,
    ensureReferralCode,
    getInviteUrl,
  } = usePlanetXStore()
  const [phase, setPhase] = useState<Phase>('scanning')
  const [statusText, setStatusText] = useState('正在扫描舰队星轨…')
  const [errorMessage, setErrorMessage] = useState('')
  const [result, setResult] = useState<FleetMatchResponse | null>(null)
  const [pendingConsensus, setPendingConsensus] = useState<MatchConsensusItem[]>([])
  const [completing, setCompleting] = useState(false)
  const [sharing, setSharing] = useState(false)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    void runMatch()
  }, [])

  async function loadPendingConsensus() {
    try {
      const data = await createGameApi(getApiClient()).listConsensus()
      setPendingConsensus(data?.pending ?? [])
    } catch {
      setPendingConsensus([])
    }
  }

  async function runMatch() {
    setPhase('scanning')
    setStatusText('正在扫描舰队星轨…')
    setErrorMessage('')
    setResult(null)
    setPendingConsensus([])

    await new Promise((r) => setTimeout(r, 900))
    setStatusText('计算人格互补轨道…')

    try {
      const data = await createGameApi(getApiClient()).match()
      if (!data?.matched || !data?.match) {
        throw new Error('匹配失败')
      }
      setResult(data)
      setPhase('result')
      void loadPendingConsensus()
    } catch (err: any) {
      setPhase('error')
      const code = err?.body?.error || err?.details?.error
      const friendlyByCode: Record<string, string> = {
        personality_required: '请先完成星际人格测试',
        fleet_required: '请先创建或加入舰队（舰队 Tab）',
        fleet_too_small: '舰队内需要至少另一名成员。复制邀请链接给队友后再试',
      }
      setErrorMessage(
        (code && friendlyByCode[code]) ||
          err?.body?.message ||
          err?.message ||
          err?.error ||
          '匹配信号中断，请稍后重试',
      )
    }
  }

  async function onConfirm() {
    if (completing || !result) return
    const ui = deriveMatchUiState(result)
    // v0：后端 can_complete_mission 优先；缺省时匹配成功即可确认
    const canComplete =
      result.can_complete_mission === true ||
      (result.can_complete_mission !== false && (ui.canComplete || result.matched === true))
    if (!canComplete) {
      setToast('契合度未达解锁阈值，可邀请更多舰员后再试')
      return
    }
    setCompleting(true)
    try {
      if (!missionsCompleted.includes('match')) {
        const ok = await completeMission('match')
        if (!ok) return
        setAchievement({
          title: '🎯 首次星际匹配！',
          desc: '你已与另一位星际公民完成匹配 · 匹配星图已解锁',
        })
      }
      // 闭环下一动机：凭证出口（信任档案）优先于空 Hub
      const done = usePlanetXStore.getState().missionsCompleted
      if (
        (['personality', 'team', 'match', 'share'] as const).every((id) => done.includes(id))
      ) {
        setScreen('trust')
      } else {
        setScreen('hub')
      }
    } finally {
      setCompleting(false)
    }
  }

  async function onShareSpread() {
    if (sharing) return
    setSharing(true)
    try {
      await ensureReferralCode()
      const url = getInviteUrl()
      const p = personalityType ?? {
        name: result?.self.personality_type ?? '星际公民',
        emoji: result?.self.personality_emoji ?? '🌌',
        tagline: '',
        desc: '',
        traits: [],
      }
      const text = getShareText('wechat', p, url)
      await navigator.clipboard?.writeText(text)
      setToast('📋 传播文案已复制！分享到微信扩大验证池')
      setScreen('result')
    } catch {
      setToast('复制失败，请手动分享邀请链接')
    } finally {
      setSharing(false)
    }
  }

  async function onAcknowledge(consensusId: string) {
    try {
      await createGameApi(getApiClient()).acknowledgeConsensus({ consensus_id: consensusId })
      setToast('已发送共识确认')
      void loadPendingConsensus()
      void runMatch()
    } catch (err: any) {
      setToast(err?.body?.message || err?.message || '确认失败，请稍后重试')
    }
  }

  const uiState = result ? deriveMatchUiState(result) : null
  const canComplete =
    !!result &&
    (result.can_complete_mission === true ||
      (result.can_complete_mission !== false &&
        (!!uiState?.canComplete || result.matched === true)))

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '8px' }}>
        <div style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', letterSpacing: '0.15em' }}>
          PLANET X · MATCH
        </div>
        <h2 style={{ margin: '8px 0 0', fontSize: '22px', fontWeight: 800, color: 'var(--px-color-accent)' }}>
          首次星际匹配
        </h2>
      </div>

      {phase === 'scanning' && (
        <div style={{ textAlign: 'center', padding: '48px 12px' }}>
          <div
            style={{
              width: 96,
              height: 96,
              margin: '0 auto 24px',
              borderRadius: '50%',
              border: '3px solid rgba(200,255,80,0.25)',
              borderTopColor: 'var(--px-color-accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 36,
              animation: 'xSpin 1.2s linear infinite',
            }}
          >
            🎯
          </div>
          <div style={{ color: 'var(--px-color-accent)', fontSize: 14, marginBottom: 8 }}>{statusText}</div>
          <div style={{ color: 'var(--px-color-text-muted)', fontSize: 12 }}>仅在舰队范围内寻找互补人格</div>
        </div>
      )}

      {phase === 'result' && result && uiState && (
        <div style={{ animation: 'fadeIn 0.35s ease' }}>
          <ConsensusBadge uiState={uiState} />

          {result.fleet_name && (
            <div
              style={{
                textAlign: 'center',
                fontSize: 12,
                color: 'var(--px-color-text-muted)',
                marginBottom: 16,
              }}
            >
              舰队 · {result.fleet_name}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <PairCard
              emoji={result.self.personality_emoji}
              role="你"
              type={result.self.personality_type}
            />
            <div style={{ width: 72, textAlign: 'center', flexShrink: 0 }}>
              <div style={{ fontSize: 28, fontWeight: 900, color: 'var(--px-color-accent)', lineHeight: 1 }}>
                {result.match.match_score}
              </div>
              <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', marginTop: 4 }}>契合度</div>
              <div style={{ fontSize: 10, color: 'var(--px-color-text-muted)', marginTop: 2 }}>
                阈值 {uiState.threshold}
              </div>
            </div>
            <PairCard
              emoji={result.match.personality_emoji}
              role={result.match.name}
              type={result.match.personality_type}
            />
          </div>

          <div
            style={{
              background: 'rgba(107,63,160,0.2)',
              border: '1px solid rgba(200,255,80,0.2)',
              borderRadius: 12,
              padding: '14px 16px',
              textAlign: 'center',
              fontSize: 13,
              marginBottom: 16,
              lineHeight: 1.5,
            }}
          >
            {result.match.reason}
          </div>

          {pendingConsensus.length > 0 && (
            <div
              style={{
                marginBottom: 16,
                padding: '12px',
                borderRadius: 12,
                border: '1px solid rgba(0,229,255,0.25)',
                background: 'rgba(0,229,255,0.05)',
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: '#00E5FF', marginBottom: 8 }}>
                待你认可的共识请求
              </div>
              {pendingConsensus.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                    marginBottom: 8,
                  }}
                >
                  <div style={{ fontSize: 12, color: 'var(--px-color-text-muted)' }}>
                    {item.candidate_name} · {item.match_score} 分
                  </div>
                  <button
                    onClick={() => void onAcknowledge(item.id)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 8,
                      border: 'none',
                      background: 'var(--px-color-accent)',
                      color: '#0a0a1a',
                      fontSize: 11,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    认可
                  </button>
                </div>
              ))}
            </div>
          )}

          {canComplete ? (
            <button
              onClick={() => void onConfirm()}
              disabled={completing}
              style={{
                width: '100%',
                padding: '14px 0',
                borderRadius: 12,
                border: 'none',
                background: 'var(--px-color-accent)',
                color: '#0a0a1a',
                fontWeight: 700,
                fontSize: 14,
                cursor: completing ? 'default' : 'pointer',
                opacity: completing ? 0.7 : 1,
                marginBottom: 10,
              }}
            >
              {completing ? '同步中…' : '确认匹配 · 解锁星图 +40 XP'}
            </button>
          ) : (
            <SpreadPanel
              uiState={uiState!}
              sharing={sharing}
              onShare={() => void onShareSpread()}
            />
          )}

          <button
            onClick={() => setScreen('hub')}
            style={{
              width: '100%',
              padding: '10px 0',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'transparent',
              color: 'var(--px-color-text-muted)',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            稍后再说
          </button>
        </div>
      )}

      {phase === 'error' && (
        <div style={{ textAlign: 'center', padding: '40px 12px' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📡</div>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>匹配信号中断</div>
          <div style={{ fontSize: 13, color: 'var(--px-color-text-muted)', marginBottom: 24, lineHeight: 1.5 }}>
            {errorMessage}
          </div>
          <button
            onClick={() => { started.current = true; void runMatch() }}
            style={{
              width: '100%',
              padding: '14px 0',
              borderRadius: 12,
              border: 'none',
              background: 'var(--px-color-accent)',
              color: '#0a0a1a',
              fontWeight: 700,
              fontSize: 14,
              cursor: 'pointer',
              marginBottom: 10,
            }}
          >
            重新扫描
          </button>
          <button
            onClick={() => setScreen('hub')}
            style={{
              width: '100%',
              padding: '10px 0',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'transparent',
              color: 'var(--px-color-text-muted)',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            返回母舰
          </button>
        </div>
      )}
    </div>
  )
}

function ConsensusBadge({ uiState }: { uiState: ReturnType<typeof deriveMatchUiState> }) {
  const colors = {
    verified: { bg: 'rgba(200,255,80,0.12)', border: 'rgba(200,255,80,0.35)', text: 'var(--px-color-accent)' },
    weak: { bg: 'rgba(249,202,36,0.1)', border: 'rgba(249,202,36,0.3)', text: '#F9CA24' },
    failed: { bg: 'rgba(255,118,117,0.1)', border: 'rgba(255,118,117,0.3)', text: '#FF7675' },
  }[uiState.view]

  return (
    <div
      style={{
        textAlign: 'center',
        marginBottom: 14,
        padding: '8px 12px',
        borderRadius: 10,
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        fontSize: 12,
        fontWeight: 700,
        color: colors.text,
        letterSpacing: '0.05em',
      }}
    >
      {uiState.statusLabel}
    </div>
  )
}

function SpreadPanel({
  uiState,
  sharing,
  onShare,
}: {
  uiState: ReturnType<typeof deriveMatchUiState>
  sharing: boolean
  onShare: () => void
}) {
  const hint = uiState.spreadHint
  const remaining = Math.max(0, hint.spread_target - hint.spread_count)

  return (
    <div
      style={{
        marginBottom: 12,
        padding: '14px',
        borderRadius: 12,
        border: '1px solid rgba(200,255,80,0.2)',
        background: 'rgba(200,255,80,0.04)',
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--px-color-accent)', marginBottom: 6 }}>
        📡 扩大验证池
      </div>
      <p style={{ fontSize: 12, color: 'var(--px-color-text-muted)', lineHeight: 1.5, margin: '0 0 10px' }}>
        {hint.message ?? '邀请更多舰员加入舰队，提升共识验证成功率'}
      </p>
      {hint.spread_target > 0 && (
        <div style={{ fontSize: 11, color: 'var(--px-color-text-muted)', marginBottom: 12 }}>
          传播进度 {hint.spread_count}/{hint.spread_target}
          {remaining > 0 ? ` · 再邀请 ${remaining} 人` : ''}
        </div>
      )}
      <button
        onClick={onShare}
        disabled={sharing}
        style={{
          width: '100%',
          padding: '14px 0',
          borderRadius: 12,
          border: 'none',
          background: 'linear-gradient(90deg, var(--px-color-purple-deep), var(--px-color-violet))',
          color: 'white',
          fontWeight: 700,
          fontSize: 14,
          cursor: sharing ? 'default' : 'pointer',
          opacity: sharing ? 0.7 : 1,
        }}
      >
        {sharing ? '生成中…' : '📡 复制传播文案 · 发送星际信号'}
      </button>
    </div>
  )
}

function PairCard({ emoji, role, type }: { emoji: string; role: string; type: string }) {
  return (
    <div
      style={{
        flex: 1,
        background: 'var(--px-color-bg-card)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 12,
        padding: '16px 10px',
        textAlign: 'center',
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: 32, marginBottom: 6 }}>{emoji}</div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--px-color-text-muted)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {role}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{type}</div>
    </div>
  )
}
