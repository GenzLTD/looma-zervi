/**
 * 信任档案页 — 小程序端 PlanetX 信任呈现。
 * 复用 @looma/shared-core 的 createTrustApi 与翻译表，
 * 与 Web features/trust/TrustScreen.tsx 同源。
 *
 * 禁止画 social 信用分，信任呈现走 attestation 卡片。
 */
import type { TrustAttestation } from "@looma/shared-core";
import {
  CLAIM_LABEL,
  STATUS_LABEL,
  STATUS_COLOR,
  EVIDENCE_LABEL,
  EVIDENCE_FALLBACK,
  CLAIM_FALLBACK,
} from "@looma/shared-core";
import { trustApi } from "../../utils/api";

interface AttestationCard {
  attestation_id: string;
  claimLabel: string;
  claimStatement: string;
  evidenceLabel: string;
  statusLabel: string;
  statusColor: string;
  issuedAt: string;
  confidenceScore: string;
}

Page({
  data: {
    attestations: [] as AttestationCard[],
    total: 0,
    loading: true,
    error: "",
  },

  onLoad() {
    this.loadAttestations();
  },

  onPullDownRefresh() {
    this.loadAttestations().finally(() => wx.stopPullDownRefresh());
  },

  async loadAttestations() {
    try {
      this.setData({ loading: true, error: "" });

      const result = await trustApi.listAttestations();

      const attestations: AttestationCard[] = (result.attestations || []).map(
        (a: TrustAttestation) => ({
          attestation_id: a.attestation_id,
          claimLabel: CLAIM_LABEL[a.claim_type] || a.claim_type || CLAIM_FALLBACK,
          claimStatement: a.claim_statement || "—",
          evidenceLabel:
            EVIDENCE_LABEL[a.evidence_type] || a.evidence_type || EVIDENCE_FALLBACK,
          statusLabel:
            STATUS_LABEL[a.verification_status] || a.verification_status || "未验证",
          statusColor:
            STATUS_COLOR[a.verification_status] || STATUS_COLOR.unverified,
          issuedAt: this.formatDate(a.issued_at),
          confidenceScore: a.confidence_score
            ? (a.confidence_score * 100).toFixed(0) + "%"
            : "—",
        })
      );

      this.setData({
        attestations,
        total: result.total ?? attestations.length,
        loading: false,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "加载失败";
      this.setData({ error: msg, loading: false });
    }
  },

  formatDate(iso: string): string {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}`;
    } catch {
      return iso.slice(0, 10);
    }
  },

  onShareAppMessage() {
    return {
      title: "我的信任档案 — PlanetX",
      path: "/pages/trust/index",
    };
  },
});
