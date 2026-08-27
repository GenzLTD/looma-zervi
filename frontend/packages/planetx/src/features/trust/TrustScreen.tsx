import { useCallback, useEffect, useState } from 'react'
import {
  createTrustApi,
  type TrustAttestation,
  CLAIM_LABEL,
  STATUS_LABEL,
  EVIDENCE_LABEL,
  EVIDENCE_FALLBACK,
  CLAIM_FALLBACK,
} from '@looma/shared-core'
import { getApiClient, usePlanetXStore } from '../auth/planetxAuthStore'
import PlanetXIcon from '../../brand/ui/PlanetXIcon'

/**
 * PlanetX C 端信任档案 — 行为证据 + 验证链（禁止画 social 信用分）
 * ENGINEERING_CLOSED_LOOP_P0 · P0-1
 */
export default function TrustScreen() {
  const setScreen = usePlanetXStore((s) => s.setScreen)
  const setToast = usePlanetXStore((s) => s.setToast)
  const [items, setItems] = useState<TrustAttestation[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const api = createTrustApi(getApiClient())
      const res = await api.listAttestations()
      setItems(res.attestations ?? [])
    } catch {
      setToast('信任档案加载失败，请稍后重试')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [setToast])

  useEffect(() => {
    void load()
  }, [load])

  const onRefresh = async () => {
    setRefreshing(true)
    try {
      const api = createTrustApi(getApiClient())
      const res = await api.refresh()
      setItems(res.attestations ?? [])
      setToast('已根据最新行为刷新声明')
    } catch {
      setToast('刷新失败')
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setScreen('hub')}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--px-color-text-muted)',
          fontSize: 13,
          cursor: 'pointer',
          padding: 0,
          marginBottom: 12,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        <PlanetXIcon name="chevron-left" size={14} color="currentColor" />
        返回 Hub
      </button>

      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: 'var(--px-color-text-muted)', letterSpacing: '0.15em' }}>
          PLANET X · TRUST
        </div>
        <h2 style={{ margin: '8px 0 0', fontSize: 22, fontWeight: 800, color: 'var(--px-color-accent)' }}>
          我的信任档案
        </h2>
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--px-color-text-muted)', lineHeight: 1.5 }}>
          这里只展示行为证据与验证声明——不是社交距离分数。
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          onClick={() => void onRefresh()}
          disabled={refreshing}
          style={{
            flex: 1,
            padding: '12px 0',
            borderRadius: 12,
            border: 'none',
            background: 'var(--px-color-accent)',
            color: '#0a0a1a',
            fontWeight: 700,
            fontSize: 13,
            cursor: refreshing ? 'default' : 'pointer',
            opacity: refreshing ? 0.7 : 1,
          }}
        >
          {refreshing ? '刷新中…' : '根据行为刷新声明'}
        </button>
        <button
          type="button"
          onClick={() => setScreen('timeline')}
          style={{
            flex: 1,
            padding: '12px 0',
            borderRadius: 12,
            border: '1px solid rgba(200,255,80,0.35)',
            background: 'rgba(200,255,80,0.08)',
            color: 'var(--px-color-accent)',
            fontWeight: 700,
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          去时间线沉淀
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 32, color: 'var(--px-color-text-muted)', fontSize: 13 }}>
          正在拉取声明…
        </div>
      )}

      {!loading && items.length === 0 && (
        <div
          style={{
            padding: 20,
            borderRadius: 16,
            border: '1px dashed rgba(255,255,255,0.15)',
            background: 'var(--px-color-bg-card)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 28, marginBottom: 8 }}>🛰️</div>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>档案还很薄</div>
          <div style={{ fontSize: 12, color: 'var(--px-color-text-muted)', lineHeight: 1.6 }}>
            完成测评、舰队协作、匹配共识或记一条时间线后，声明会在这里长出来。
          </div>
          <button
            type="button"
            onClick={() => setScreen('timeline')}
            style={{
              marginTop: 14,
              padding: '10px 16px',
              borderRadius: 10,
              border: 'none',
              background: 'var(--px-color-purple-deep)',
              color: '#fff',
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            先去时间线记一笔
          </button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((att) => {
          const verified =
            att.verification_status === 'verified' ||
            att.verification_status === 'verified_by_authority'
          return (
            <article
              key={att.attestation_id}
              style={{
                background: 'var(--px-color-bg-card)',
                border: `1px solid ${verified ? 'rgba(200,255,80,0.35)' : 'rgba(255,255,255,0.1)'}`,
                borderRadius: 14,
                padding: 14,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
                <span style={{ fontWeight: 800, fontSize: 14 }}>
                  {CLAIM_LABEL[att.claim_type] || att.claim_type || CLAIM_FALLBACK}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 999,
                    background: verified ? 'rgba(200,255,80,0.15)' : 'rgba(255,255,255,0.06)',
                    color: verified ? 'var(--px-color-accent)' : 'var(--px-color-text-muted)',
                  }}
                >
                  {STATUS_LABEL[att.verification_status] || att.verification_status}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: 'var(--px-color-text-bright)' }}>
                {att.claim_statement}
              </p>
              <div style={{ marginTop: 10, fontSize: 11, color: 'var(--px-color-text-muted)' }}>
                证据：{EVIDENCE_LABEL[att.evidence_type] || att.evidence_type || EVIDENCE_FALLBACK}
                {att.issued_at
                  ? ` · ${new Date(att.issued_at).toLocaleDateString()}`
                  : ''}
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
