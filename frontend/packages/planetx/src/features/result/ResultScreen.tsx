import { useEffect, useRef } from 'react'
import { usePlanetXStore } from '../auth/planetxAuthStore'
import SharePanel from '../../brand/components/SharePanel'
import PlanetXMicroFeedback from '../../brand/components/PlanetXMicroFeedback'
import { px } from '../../brand/tokenUtils'

/**
 * 测评结果屏幕 — 人格类型展示 + 多平台分享 + 卡片导出
 */
export default function ResultScreen() {
  const { personalityType, finishQuiz, setScreen, setToast, quizFinished } = usePlanetXStore()
  const hasFinished = useRef(false)

  useEffect(() => {
    if (!hasFinished.current && !quizFinished) {
      hasFinished.current = true
      finishQuiz()
    }
  }, [finishQuiz, quizFinished])

  const p = personalityType
  if (!p) return null

  const handleExport = () => {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const w = 750, h = 1000
    canvas.width = w; canvas.height = h

    // Background
    const grad = ctx.createLinearGradient(0, 0, w, h)
    grad.addColorStop(0, px.bgCard)
    grad.addColorStop(0.5, px.bgPurple)
    grad.addColorStop(1, px.bgGreen)
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, w, h)

    // Glow
    const g1 = ctx.createRadialGradient(w * 0.3, h * 0.35, 0, w * 0.3, h * 0.35, 300)
    g1.addColorStop(0, 'rgba(200,255,80,0.06)'); g1.addColorStop(1, 'transparent')
    ctx.fillStyle = g1; ctx.fillRect(0, 0, w, h)

    ctx.font = '120px sans-serif'; ctx.textAlign = 'center'
    ctx.fillText(p.emoji, w / 2, 180)
    ctx.font = 'bold 52px "PingFang SC","Microsoft YaHei",sans-serif'
    ctx.fillStyle = px.accent; ctx.shadowColor = 'rgba(200,255,80,0.4)'; ctx.shadowBlur = 30
    ctx.fillText(p.name, w / 2, 280); ctx.shadowBlur = 0
    ctx.font = '24px "PingFang SC","Microsoft YaHei",sans-serif'
    ctx.fillStyle = px.textMuted; ctx.fillText(p.tagline, w / 2, 340)

    // Traits
    ctx.font = '22px "PingFang SC","Microsoft YaHei",sans-serif'
    p.traits.forEach((t, i) => {
      const tx = w / 2 - ((p.traits.length * 140) / 2) + 70 + i * 140
      ctx.fillStyle = 'rgba(107,63,160,0.3)'; ctx.beginPath()
      ctx.roundRect(tx - (ctx.measureText(t).width + 40) / 2, 440, ctx.measureText(t).width + 40, 36, 18)
      ctx.fill(); ctx.fillStyle = px.primarySoft; ctx.fillText(t, tx, 466)
    })

    // Desc
    ctx.font = '22px "PingFang SC","Microsoft YaHei",sans-serif'
    ctx.fillStyle = px.textMuted
    let lineY = 540
    const maxW = 600
    p.desc.split('').reduce((line: string, char: string) => {
      const test = line + char
      if (ctx.measureText(test).width > maxW) {
        ctx.fillText(line, w / 2, lineY)
        lineY += 40
        return char
      }
      return test
    }, '')

    // QR placeholder
    ctx.fillStyle = 'rgba(200,255,80,0.05)'; ctx.beginPath()
    ctx.roundRect(w / 2 - 80, lineY + 60, 160, 160, 16); ctx.fill()
    ctx.strokeStyle = 'rgba(200,255,80,0.2)'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]); ctx.stroke(); ctx.setLineDash([])
    ctx.font = '18px "PingFang SC","Microsoft YaHei",sans-serif'
    ctx.fillStyle = px.textMuted; ctx.fillText('📱 扫码加入舰队', w / 2, lineY + 145)
    ctx.font = '16px "PingFang SC","Microsoft YaHei",sans-serif'
    ctx.fillStyle = 'rgba(184,184,200,0.3)'; ctx.fillText('PLANET X · 星际人格认证', w / 2, h - 40)

    canvas.toBlob((blob) => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `PlanetX_${p.name}.png`; a.click()
      URL.revokeObjectURL(url)
      setToast('📸 卡片已保存！去朋友圈晒出你的星际身份')
    }, 'image/png')
  }

  return (
    <div>
      <div
        style={{
          background: 'var(--px-color-bg-card)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '16px',
          padding: '24px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: '48px', marginBottom: '8px' }}>{p.emoji}</div>
        <div style={{ fontSize: '18px', fontWeight: 900, color: 'var(--px-color-accent)' }}>{p.name}</div>
        <div style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', letterSpacing: '1px', marginTop: '4px' }}>{p.tagline}</div>
        <div
          style={{
            marginTop: 10,
            display: 'inline-block',
            fontSize: 11,
            padding: '4px 10px',
            borderRadius: 999,
            background: 'rgba(255,180,80,0.12)',
            color: 'rgba(255,200,120,0.95)',
          }}
        >
          初始假设 · 将随行为沉淀被修正
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', justifyContent: 'center', margin: '16px 0' }}>
          {p.traits.map((t, i) => (
            <span
              key={i}
              style={{
                padding: '4px 12px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: 600,
                background: 'rgba(107,63,160,0.2)',
                color: 'var(--px-color-primary-soft)',
              }}
            >
              {t}
            </span>
          ))}
        </div>
        <p style={{ fontSize: '14px', color: 'var(--px-color-text-muted)', lineHeight: 1.6, marginBottom: '16px' }}>{p.desc}</p>

        {/* Share Preview */}
        <div
          style={{
            background: 'linear-gradient(135deg, var(--px-color-bg-card) 0%, var(--px-color-bg-purple) 50%, var(--px-color-bg-green) 100%)',
            border: '2px solid rgba(255,255,255,0.1)',
            borderRadius: '16px',
            padding: '20px',
            textAlign: 'center',
            position: 'relative',
            overflow: 'hidden',
            marginBottom: '16px',
          }}
        >
          <div style={{ fontSize: '48px', position: 'relative', zIndex: 10 }}>{p.emoji}</div>
          <div style={{ fontSize: '18px', fontWeight: 900, color: 'var(--px-color-accent)', position: 'relative', zIndex: 10 }}>{p.name}</div>
          <div style={{ fontSize: '12px', color: 'var(--px-color-text-muted)', position: 'relative', zIndex: 10 }}>PlanetX · 初始假设（行为将更新它）</div>
          <div
            style={{
              width: '80px', height: '80px', margin: '12px auto 0',
              background: 'rgba(200,255,80,0.05)',
              border: '1px dashed rgba(200,255,80,0.2)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              color: 'var(--px-color-text-muted)',
              position: 'relative',
              zIndex: 10,
            }}
          >
            📱 扫码加入舰队
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button
            onClick={handleExport}
            style={{
              padding: '12px 0',
              borderRadius: '16px',
              fontWeight: 'bold',
              fontSize: '14px',
              color: 'var(--px-color-accent)',
              border: '1px solid rgba(200,255,80,0.3)',
              background: 'rgba(200,255,80,0.05)',
              cursor: 'pointer',
              transition: 'all 0.2s',
              width: '100%',
            }}
          >
            📸 保存分享卡片图片
          </button>
          <button
            onClick={() => setScreen('timeline')}
            style={{
              padding: '12px 0',
              borderRadius: '16px',
              fontWeight: 'bold',
              fontSize: '14px',
              color: 'var(--px-color-accent)',
              border: '1px solid rgba(200,255,80,0.2)',
              background: 'transparent',
              cursor: 'pointer',
              width: '100%',
            }}
          >
            🌀 查看职业时间线
          </button>
          <button
            onClick={() => setScreen('hub')}
            style={{
              padding: '12px 0',
              borderRadius: '16px',
              fontWeight: 'bold',
              fontSize: '14px',
              color: 'white',
              background: 'linear-gradient(90deg, var(--px-color-purple-deep), var(--px-color-violet))',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 0.2s',
              width: '100%',
            }}
          >
            🚀 返回母舰 · 继续探险
          </button>
        </div>
      </div>

      <SharePanel />
      <PlanetXMicroFeedback />
    </div>
  )
}
