import { useState, useCallback, useEffect } from 'react'
import { usePlanetXStore, getShareText, getApiClient } from '../../features/auth/planetxAuthStore'
import { CLOSED_LOOP_EVENTS, trackEvent } from '@looma/shared-core'
import { useConsent } from '../../compliance/useConsent'

type SharePlatform = 'wechat' | 'xiaohongshu' | 'weibo' | 'copy'

const PLATFORMS: { id: SharePlatform; icon: string; name: string; tag: string }[] = [
  { id: 'wechat', icon: '💬', name: '微信', tag: '朋友圈/群聊' },
  { id: 'xiaohongshu', icon: '📕', name: '小红书', tag: '带话题标签' },
  { id: 'weibo', icon: '📢', name: '微博', tag: '超话扩散' },
  { id: 'copy', icon: '📋', name: '复制文案', tag: '通用版本' },
]

/**
 * 多平台分享面板：
 *   - 邀请好友码（?ref=，invite_codes / tier_grant≠profile_share）
 *   - 候选人分享链接（TSpace /candidate/share/，tier_grant=profile_share）
 * 信任核验码（sc_…）在 TSpace Trust，不在此面板。
 */
export default function SharePanel() {
  const [show, setShow] = useState(false)
  const [activePlatform, setActivePlatform] = useState<SharePlatform>('wechat')
  const [inviteUrl, setInviteUrl] = useState('')
  const [hrUrl, setHrUrl] = useState('')
  const {
    personalityType,
    setToast,
    completeMission,
    ensureReferralCode,
    ensureProfileShareCode,
    getInviteUrl,
    getHrShareUrl,
  } = usePlanetXStore()

  const { ensureConsent, consentPrompt } = useConsent(getApiClient)

  const p = personalityType ?? { name: '未知', emoji: '🌌', tagline: '', desc: '', traits: [] }

  useEffect(() => {
    if (!show) return
    void (async () => {
      await ensureReferralCode()
      await ensureProfileShareCode()
      setInviteUrl(getInviteUrl())
      setHrUrl(getHrShareUrl())
    })()
  }, [show, ensureReferralCode, ensureProfileShareCode, getInviteUrl, getHrShareUrl])

  const shareText = getShareText(activePlatform, p, inviteUrl || getInviteUrl())

  const handlePlatformSelect = useCallback((platform: SharePlatform) => {
    setActivePlatform(platform)
    const url = inviteUrl || getInviteUrl()
    const text = getShareText(platform, p, url)
    navigator.clipboard?.writeText(text).then(() => {
      setToast(`📋 ${PLATFORMS.find((fp) => fp.id === platform)?.name}文案已复制！`)
      completeMission('share')
    }).catch(() => {})
  }, [p, inviteUrl, getInviteUrl, setToast, completeMission])

  const handleCopyHrLink = useCallback(async () => {
    const allowed = await ensureConsent('profile_share')
    if (!allowed) {
      setToast('需要授权后才能复制候选人分享链接')
      return
    }
    await ensureProfileShareCode()
    const url = getHrShareUrl()
    setHrUrl(url)
    if (!url) {
      setToast('请先登录后再分享')
      return
    }
    navigator.clipboard?.writeText(url).then(() => {
      setToast('🔗 候选人分享链接已复制！发送给 HR 即可在 TSpace 查看画像')
      const code = url.split('/candidate/share/')[1]?.split(/[?#]/)[0]
      trackEvent(CLOSED_LOOP_EVENTS.SHARE_LINK_COPIED, {
        share_code: code,
        properties: { channel: 'hr_link' },
      })
    }).catch(() => {})
  }, [ensureConsent, ensureProfileShareCode, getHrShareUrl, setToast])

  if (!show) {
    return (
      <>
      {consentPrompt}
      <div style={{ textAlign: 'center', marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
        <button
          onClick={() => setShow(true)}
          style={{
            padding: '10px 24px',
            borderRadius: '16px',
            fontWeight: 'bold',
            fontSize: '14px',
            color: '#C8FF50',
            border: '1px solid rgba(200,255,80,0.3)',
            background: 'rgba(200,255,80,0.05)',
            cursor: 'pointer',
          }}
        >
          📡 邀请好友（裂变链接）
        </button>
        <button
          onClick={async () => {
            setShow(true)
            await handleCopyHrLink()
          }}
          style={{
            padding: '8px 20px',
            borderRadius: '16px',
            fontSize: '13px',
            color: '#A78BFA',
            border: '1px solid rgba(167,139,250,0.3)',
            background: 'rgba(167,139,250,0.05)',
            cursor: 'pointer',
          }}
        >
          👔 候选人分享码（给 HR）
        </button>
      </div>
      </>
    )
  }

  return (
    <>
    {consentPrompt}
    <div
      style={{
        background: '#0D0D1A',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: '16px',
        padding: '16px',
        marginTop: '12px',
      }}
    >
      <h3 style={{ fontSize: '14px', color: '#B8B8C8', textAlign: 'center', marginBottom: '12px' }}>
        📡 选择频道发送邀请好友链接
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
        {PLATFORMS.map((pf) => (
          <button
            key={pf.id}
            onClick={() => handlePlatformSelect(pf.id)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              padding: '12px',
              borderRadius: '12px',
              fontSize: '12px',
              border: `1px solid ${activePlatform === pf.id ? '#C8FF50' : 'rgba(255,255,255,0.1)'}`,
              background: activePlatform === pf.id ? 'rgba(200,255,80,0.05)' : '#1A1A2E',
              cursor: 'pointer',
              color: '#B8B8C8',
            }}
          >
            <span style={{ fontSize: '24px' }}>{pf.icon}</span>
            <span>{pf.name}</span>
          </button>
        ))}
      </div>

      <div style={{ marginBottom: '12px', padding: '10px', borderRadius: '8px', background: '#1A1A2E', border: '1px solid rgba(167,139,250,0.2)' }}>
        <p style={{ fontSize: '11px', color: '#A78BFA', marginBottom: '6px' }}>
          👔 候选人分享链接（TSpace · 非信任核验码）
        </p>
        <p style={{ fontSize: '11px', color: '#888', wordBreak: 'break-all', marginBottom: '8px' }}>
          {hrUrl || '生成中…'}
        </p>
        <button
          onClick={() => void handleCopyHrLink()}
          style={{
            width: '100%',
            padding: '8px',
            borderRadius: '8px',
            fontSize: '12px',
            color: '#C4B5FD',
            border: '1px solid rgba(167,139,250,0.3)',
            background: 'transparent',
            cursor: 'pointer',
          }}
        >
          复制候选人分享链接
        </button>
      </div>

      <div
        style={{
          background: '#1A1A2E',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '8px',
          padding: '12px',
          maxHeight: '112px',
          overflowY: 'auto',
        }}
      >
        <pre style={{
          fontSize: '12px',
          color: '#B8B8C8',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          fontFamily: 'system-ui, sans-serif',
          margin: 0,
        }}>
          {shareText}
        </pre>
      </div>
    </div>
    </>
  )
}
