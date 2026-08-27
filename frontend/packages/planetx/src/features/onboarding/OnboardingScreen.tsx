import { useNavigate } from 'react-router-dom'
import { usePlanetXStore, IDENTITY_LABELS } from '../auth/planetxAuthStore'
import type { Identity } from '../auth/planetxAuthStore'
import PlanetXCard from '../../brand/ui/PlanetXCard'
import PlanetXButton from '../../brand/ui/PlanetXButton'

/**
 * 身份选择屏幕 — 星际身份三选一 + T空间入口
 * 使用 PlanetX 品牌组件重构
 */
export default function OnboardingScreen() {
  const { setIdentity, setScreen } = usePlanetXStore()
  const navigate = useNavigate()

  const handleEnterTSpace = () => {
    navigate('/tspace')
  }

  const handleSelect = (type: Identity) => {
    setIdentity(type)
    setScreen('hub')
  }

  const cards: { type: Identity; emoji: string; desc: string; tag: { text: string; bg: string; color: string } }[] = [
    {
      type: 'explorer', emoji: '🚀',
      desc: '正在寻找新的职业星球 · 渴望找到属于自己的轨道',
      tag: { text: '🔥 最多人选择', bg: 'rgba(255,45,149,0.15)', color: 'var(--px-color-pink)' },
    },
    {
      type: 'captain', emoji: '👨‍✈️',
      desc: '组建你的3人舰队 · 带领船员探索未知星域',
      tag: { text: '👥 组队模式', bg: 'rgba(0,229,255,0.15)', color: 'var(--px-color-cyan)' },
    },
    {
      type: 'wanderer', emoji: '🌌',
      desc: '不着急着陆 · 先在各个星球间随意漂流看看',
      tag: { text: '✨ 佛系模式', bg: 'rgba(255,45,149,0.15)', color: 'var(--px-color-pink)' },
    },
  ]

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 900, color: 'var(--px-color-accent)', letterSpacing: '2px', margin: 0 }}>
          Planet
          <span
            style={{
              color: 'var(--px-color-purple-deep)',
              display: 'inline-block',
              animation: 'xSpin 8s linear infinite',
            }}
          >
            X
          </span>
        </h1>
        <p style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', letterSpacing: '0.2em', marginTop: '4px' }}>
          选择你的星际身份
        </p>
        <p
          style={{
            fontSize: '12px',
            color: 'var(--px-color-text-muted)',
            lineHeight: 1.65,
            margin: '12px auto 0',
            maxWidth: 320,
          }}
        >
          这里不是投简历的地方。先看清你在做什么、和谁共事过；画像会随着记录变准，机会是后面的事。
        </p>
      </div>

      <p style={{ textAlign: 'center', fontSize: '18px', fontWeight: 'bold', marginBottom: 'var(--px-spacing-lg)' }}>
        你正在寻找什么？
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--px-spacing-md)' }}>
        {cards.map((c) => (
          <PlanetXCard
            key={c.type}
            onClick={() => handleSelect(c.type)}
            highlighted={c.type === 'explorer'}
            padding="md"
          >
            <div style={{ fontSize: '32px', marginBottom: 'var(--px-spacing-sm)' }}>{c.emoji}</div>
            <div style={{ fontSize: '18px', fontWeight: 'bold' }}>{IDENTITY_LABELS[c.type].split('·')[0]}</div>
            <div style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', marginTop: 'var(--px-spacing-xs)' }}>{c.desc}</div>
            <span
              style={{
                display: 'inline-block',
                marginTop: 'var(--px-spacing-sm)',
                padding: '4px 12px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: 600,
                background: c.tag.bg,
                color: c.tag.color,
              }}
            >
              {c.tag.text}
            </span>
          </PlanetXCard>
        ))}
      </div>

      {/* T空间入口 */}
      <div style={{ 
        textAlign: 'center', 
        marginTop: 'var(--px-spacing-lg)', 
        paddingTop: 'var(--px-spacing-md)', 
        borderTop: '1px solid rgba(255,255,255,0.1)' 
      }}>
        <div style={{ marginBottom: 'var(--px-spacing-xs)' }}>
          <PlanetXButton
            variant="accent"
            onClick={handleEnterTSpace}
            leftIcon="🪐"
          >
            进入 T 空间 · Navigator 叙事体验
          </PlanetXButton>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', marginTop: 'var(--px-spacing-xs)', opacity: 0.6 }}>
          与 AI 向导对话 · 探索六域 · 10分钟叙事体验
        </p>
      </div>
    </div>
  )
}
