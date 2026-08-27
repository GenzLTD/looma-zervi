/**
 * Trust Profile — attestation cards + share_code management (P0.5).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  createTrustApi,
  type TrustAttestation,
  type TrustAuditLogEntry,
  type TrustShareCode,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useConsent } from "../../compliance/useConsent";
import {
  AttestationCard,
  CLAIM_ORDER,
  parseScope,
  sortAttestations,
  type ClaimType,
} from "./attestationUi";

function verifyUrl(code: string): string {
  const base = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");
  const path = `${base}/verify?code=${encodeURIComponent(code)}`;
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path.startsWith("/") ? path : `/${path}`}`;
}

export default function TrustProfile() {
  const { t } = useTranslation();
  const client = useMemo(() => createSaasApiClient(), []);
  const api = useMemo(() => createTrustApi(client), [client]);
  const { ensureConsent, consentPrompt } = useConsent(() => client);

  const [attestations, setAttestations] = useState<TrustAttestation[]>([]);
  const [shareCodes, setShareCodes] = useState<TrustShareCode[]>([]);
  const [auditLogs, setAuditLogs] = useState<TrustAuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastCode, setLastCode] = useState<string | null>(null);
  const [scopeSel, setScopeSel] = useState<Record<ClaimType, boolean>>({
    identity: true,
    collaboration: true,
    communication: false,
    influence: false,
  });

  const claimLabel = (type: string) => {
    const key = `trust.claim.${type}`;
    const translated = t(key);
    return translated === key ? type : translated;
  };
  const statusLabel = (status: string) => {
    const key = `trust.status.${status}`;
    const translated = t(key);
    return translated === key ? status : translated;
  };
  const evidenceLabel = (type: string) => {
    const key = `trust.evidenceType.${type}`;
    const translated = t(key);
    return translated === key ? type : translated;
  };

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [attRes, codesRes, auditRes] = await Promise.all([
        api.listAttestations(),
        api.listShareCodes(),
        api.auditLog(20),
      ]);
      setAttestations(sortAttestations(attRes.attestations ?? []));
      setShareCodes(codesRes.share_codes ?? []);
      setAuditLogs(auditRes.audit_logs ?? []);
    } catch (err) {
      const msg =
        err instanceof ApiError && err.body?.message
          ? String(err.body.message)
          : t("trust.loadFailed");
      setError(msg);
      setAttestations([]);
    } finally {
      setLoading(false);
    }
  }, [api, t]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const res = await api.refresh();
      setAttestations(sortAttestations(res.attestations ?? []));
    } catch (err) {
      const msg =
        err instanceof ApiError && err.body?.message
          ? String(err.body.message)
          : t("trust.refreshFailed");
      setError(msg);
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreateCode = async () => {
    const scope = CLAIM_ORDER.filter((c) => scopeSel[c]);
    if (scope.length === 0) {
      setError(t("trust.shareScopeRequired"));
      return;
    }
    if (attestations.length === 0) {
      setError(t("trust.shareNeedAttestations"));
      return;
    }
    const allowed = await ensureConsent("profile_share");
    if (!allowed) {
      setError(t("trust.shareConsentRequired"));
      return;
    }
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.createShareCode({
        scope,
        max_access_count: 10,
        expires_in_seconds: 7 * 24 * 3600,
      });
      setLastCode(res.share_code);
      setNotice(t("trust.shareCreated"));
      const codesRes = await api.listShareCodes();
      setShareCodes(codesRes.share_codes ?? []);
    } catch (err) {
      const msg =
        err instanceof ApiError && err.body?.message
          ? String(err.body.message)
          : t("trust.shareCreateFailed");
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(t("trust.copied"));
    } catch {
      setNotice(text);
    }
  };

  const handleRevoke = async (id: string) => {
    setError(null);
    try {
      await api.revokeShareCode(id);
      setNotice(t("trust.shareRevoked"));
      const codesRes = await api.listShareCodes();
      setShareCodes(codesRes.share_codes ?? []);
    } catch (err) {
      const msg =
        err instanceof ApiError && err.body?.message
          ? String(err.body.message)
          : t("trust.shareRevokeFailed");
      setError(msg);
    }
  };

  const renderAttestation = (att: TrustAttestation) => (
    <AttestationCard
      key={att.attestation_id}
      att={att}
      claimLabel={claimLabel(att.claim_type)}
      statusLabel={statusLabel(att.verification_status)}
      evidenceLabel={evidenceLabel(att.evidence_type)}
      confidenceHint={t("trust.confidenceHint", {
        pct: Math.round((att.confidence_score ?? 0) * 100),
      })}
      evidencePrefix={`${t("trust.evidenceLabel")}: `}
      issuedPrefix={`${t("trust.issuedLabel")}: `}
      signedLabel={t("trust.signed")}
    />
  );

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {consentPrompt}
      <header className="space-y-2">
        <h1
          className="text-2xl font-bold m-0"
          style={{ color: "var(--color-text-primary)" }}
        >
          {t("trust.title")}
        </h1>
        <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }}>
          {t("trust.subtitle")}
        </p>
      </header>

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <p className="text-sm m-0" style={{ color: "var(--color-text-muted)" }}>
            {loading
              ? t("trust.loading")
              : t("trust.count", { count: attestations.length })}
          </p>
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={loading || refreshing}
            className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-50"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            {refreshing ? t("trust.refreshing") : t("trust.refresh")}
          </button>
        </div>

        {error && (
          <p className="text-sm m-0" style={{ color: "var(--color-danger)" }}>
            {error}
          </p>
        )}
        {notice && (
          <p className="text-sm m-0" style={{ color: "var(--color-success)" }}>
            {notice}
          </p>
        )}

        {!loading && attestations.length === 0 && (
          <div
            className="rounded-lg p-6 space-y-3"
            style={{
              backgroundColor: "var(--color-bg-card)",
              border: "1px dashed #e0e0e0",
            }}
          >
            <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }}>
              {t("trust.empty")}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/jobs"
                className="text-sm no-underline"
                style={{ color: "var(--color-primary)" }}
              >
                {t("trust.ctaJobs")}
              </Link>
              <Link
                to="/resume"
                className="text-sm no-underline"
                style={{ color: "var(--color-primary)" }}
              >
                {t("trust.ctaResume")}
              </Link>
            </div>
          </div>
        )}

        <div className="space-y-3">{attestations.map(renderAttestation)}</div>
      </section>

      {/* Share codes */}
      <section className="space-y-4">
        <h2
          className="text-lg font-semibold m-0"
          style={{ color: "var(--color-text-primary)" }}
        >
          {t("trust.shareTitle")}
        </h2>
        <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }}>
          {t("trust.shareHint")}
        </p>

        <div className="flex flex-wrap gap-3">
          {CLAIM_ORDER.map((c) => (
            <label
              key={c}
              className="flex items-center gap-2 text-sm cursor-pointer"
              style={{ color: "var(--color-text-secondary)" }}
            >
              <input
                type="checkbox"
                checked={scopeSel[c]}
                onChange={(e) =>
                  setScopeSel((prev) => ({ ...prev, [c]: e.target.checked }))
                }
              />
              {claimLabel(c)}
            </label>
          ))}
        </div>

        <button
          type="button"
          onClick={() => void handleCreateCode()}
          disabled={creating || loading}
          className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-50"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          {creating ? t("trust.shareCreating") : t("trust.shareCreate")}
        </button>

        {lastCode && (
          <div
            className="rounded-lg p-4 space-y-2"
            style={{
              backgroundColor: "var(--color-bg-surface)",
              border: "1px solid #e8e8e8",
            }}
          >
            <p className="text-sm m-0 font-mono" style={{ color: "var(--color-text-primary)" }}>
              {lastCode}
            </p>
            <p className="text-xs m-0 break-all" style={{ color: "var(--color-text-muted)" }}>
              {verifyUrl(lastCode)}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="text-xs px-3 py-1.5 rounded border cursor-pointer bg-transparent"
                style={{ borderColor: "#e0e0e0", color: "var(--color-primary)" }}
                onClick={() => void handleCopy(lastCode)}
              >
                {t("trust.copyCode")}
              </button>
              <button
                type="button"
                className="text-xs px-3 py-1.5 rounded border cursor-pointer bg-transparent"
                style={{ borderColor: "#e0e0e0", color: "var(--color-primary)" }}
                onClick={() => void handleCopy(verifyUrl(lastCode))}
              >
                {t("trust.copyLink")}
              </button>
              <Link
                to={`/verify?code=${encodeURIComponent(lastCode)}`}
                className="text-xs px-3 py-1.5 rounded border no-underline"
                style={{ borderColor: "#e0e0e0", color: "var(--color-text-secondary)" }}
              >
                {t("trust.openVerify")}
              </Link>
            </div>
          </div>
        )}

        <div className="space-y-2">
          {shareCodes.length === 0 ? (
            <p className="text-sm m-0" style={{ color: "var(--color-text-muted)" }}>
              {t("trust.shareEmpty")}
            </p>
          ) : (
            shareCodes.map((sc) => {
              const scope = parseScope(sc.scope);
              const remaining = Math.max(
                0,
                (sc.max_access_count ?? 0) - (sc.access_count ?? 0),
              );
              return (
                <div
                  key={sc.id}
                  className="rounded-lg p-3 flex flex-wrap items-center justify-between gap-2"
                  style={{
                    backgroundColor: "var(--color-bg-card)",
                    border: "1px solid #f0f0f0",
                  }}
                >
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm m-0 font-mono" style={{ color: "var(--color-text-primary)" }}>
                      {sc.code}
                    </p>
                    <p className="text-xs m-0" style={{ color: "var(--color-text-muted)" }}>
                      {t("trust.shareMeta", {
                        status: sc.status,
                        remaining,
                        expires: sc.expires_at
                          ? new Date(sc.expires_at).toLocaleString()
                          : "—",
                        scope: scope.map(claimLabel).join("、") || "—",
                      })}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {sc.status === "active" && (
                      <>
                        <button
                          type="button"
                          className="text-xs px-2 py-1 rounded border cursor-pointer bg-transparent"
                          style={{ borderColor: "#e0e0e0", color: "var(--color-primary)" }}
                          onClick={() => void handleCopy(verifyUrl(sc.code))}
                        >
                          {t("trust.copyLink")}
                        </button>
                        <button
                          type="button"
                          className="text-xs px-2 py-1 rounded border cursor-pointer bg-transparent"
                          style={{ borderColor: "#e0e0e0", color: "var(--color-danger)" }}
                          onClick={() => void handleRevoke(sc.id)}
                        >
                          {t("trust.revoke")}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* Audit */}
      <section className="space-y-3">
        <h2
          className="text-lg font-semibold m-0"
          style={{ color: "var(--color-text-primary)" }}
        >
          {t("trust.auditTitle")}
        </h2>
        {auditLogs.length === 0 ? (
          <p className="text-sm m-0" style={{ color: "var(--color-text-muted)" }}>
            {t("trust.auditEmpty")}
          </p>
        ) : (
          <ul className="space-y-2 list-none p-0 m-0">
            {auditLogs.map((log) => (
              <li
                key={log.id}
                className="text-xs rounded p-2"
                style={{
                  backgroundColor: "var(--color-bg-surface)",
                  color: "var(--color-text-muted)",
                }}
              >
                {t("trust.auditRow", {
                  time: log.created_at
                    ? new Date(log.created_at).toLocaleString()
                    : "—",
                  code: log.share_code,
                  result: log.result,
                })}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs m-0" style={{ color: "var(--color-text-muted)" }}>
        {t("trust.noScoreNote")}
      </p>
    </div>
  );
}
