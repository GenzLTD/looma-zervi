/**
 * Public trust verify page — no login; authorised by share_code.
 * Route: /verify?code=sc_…
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  createTrustApi,
  type TrustAttestation,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { AttestationCard, sortAttestations } from "./attestationUi";

export default function TrustVerify() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const codeFromUrl = (searchParams.get("code") || "").trim();
  const [input, setInput] = useState(codeFromUrl);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alias, setAlias] = useState<string | null>(null);
  const [verifiedAt, setVerifiedAt] = useState<string | null>(null);
  const [scope, setScope] = useState<string[]>([]);
  const [attestations, setAttestations] = useState<TrustAttestation[]>([]);

  const api = useMemo(
    () =>
      createTrustApi(
        createSaasApiClient({
          getToken: () => null,
          onUnauthorized: () => undefined,
        }),
      ),
    [],
  );

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

  const runVerify = useCallback(
    async (rawCode: string) => {
      const share_code = rawCode.trim();
      if (!share_code) {
        setError(t("trustVerify.codeRequired"));
        return;
      }
      setLoading(true);
      setError(null);
      setAttestations([]);
      setAlias(null);
      try {
        const res = await api.verify({ share_code });
        setAttestations(sortAttestations(res.attestations ?? []));
        setAlias(res.candidate_alias ?? null);
        setVerifiedAt(res.verified_at ?? null);
        setScope(res.share_code_scope ?? res.scope ?? []);
        if (share_code !== codeFromUrl) {
          setSearchParams({ code: share_code }, { replace: true });
        }
      } catch (err) {
        let msg = t("trustVerify.failed");
        if (err instanceof ApiError) {
          const code = err.body?.error || err.body?.code;
          if (code === "share_code_not_found") msg = t("trustVerify.notFound");
          else if (code === "share_code_revoked") msg = t("trustVerify.revoked");
          else if (code === "share_code_expired") msg = t("trustVerify.expired");
          else if (code === "share_code_exhausted") msg = t("trustVerify.exhausted");
          else if (err.body?.message) msg = String(err.body.message);
        }
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [api, codeFromUrl, setSearchParams, t],
  );

  useEffect(() => {
    if (codeFromUrl) {
      setInput(codeFromUrl);
      void runVerify(codeFromUrl);
    }
    // Auto-run once when URL has code
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional mount/URL sync
  }, [codeFromUrl]);

  return (
    <div className="max-w-3xl mx-auto space-y-6 py-2">
      <header className="space-y-2">
        <h1
          className="text-2xl font-bold m-0"
          style={{ color: "var(--color-text-primary)" }}
        >
          {t("trustVerify.title")}
        </h1>
        <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }}>
          {t("trustVerify.subtitle")}
        </p>
      </header>

      <form
        className="flex flex-wrap gap-2 items-end"
        onSubmit={(e) => {
          e.preventDefault();
          void runVerify(input);
        }}
      >
        <label className="flex-1 min-w-[200px] space-y-1">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {t("trustVerify.codeLabel")}
          </span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="sc_…"
            className="w-full px-3 py-2 text-sm rounded-lg border outline-none"
            style={{
              borderColor: "#e0e0e0",
              backgroundColor: "var(--color-bg-surface)",
              color: "var(--color-text-primary)",
            }}
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-50"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          {loading ? t("trustVerify.verifying") : t("trustVerify.submit")}
        </button>
      </form>

      {error && (
        <p className="text-sm m-0" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      )}

      {alias && !error && (
        <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }}>
          {t("trustVerify.resultFor", { name: alias })}
          {verifiedAt
            ? ` · ${t("trustVerify.verifiedAt", {
                date: new Date(verifiedAt).toLocaleString(),
              })}`
            : ""}
          {scope.length > 0
            ? ` · ${t("trustVerify.scope", {
                scope: scope.map(claimLabel).join("、"),
              })}`
            : ""}
        </p>
      )}

      <div className="space-y-3">
        {attestations.map((att) => (
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
            signedLabel={
              att.signature
                ? t("trustVerify.sigPresent")
                : t("trustVerify.sigMissing")
            }
            signatureOk={att.signature ? true : false}
          />
        ))}
      </div>

      {!loading && !error && attestations.length === 0 && alias && (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {t("trustVerify.emptyAttestations")}
        </p>
      )}

      <p className="text-xs m-0" style={{ color: "var(--color-text-muted)" }}>
        {t("trustVerify.footer")}{" "}
        <Link to="/trust" style={{ color: "var(--color-primary)" }}>
          {t("trustVerify.ownerLink")}
        </Link>
      </p>
    </div>
  );
}
