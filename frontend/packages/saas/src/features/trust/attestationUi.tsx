/**
 * Shared attestation card for trust profile + public verify page.
 */
import type { TrustAttestation } from "@looma/shared-core";

export const CLAIM_ORDER = [
  "identity",
  "collaboration",
  "communication",
  "influence",
] as const;

export type ClaimType = (typeof CLAIM_ORDER)[number];

export function statusTone(status: string): { bg: string; fg: string } {
  if (status === "verified" || status === "verified_by_authority") {
    return { bg: "#e8f5e9", fg: "var(--color-success)" };
  }
  if (status === "weak") {
    return { bg: "#fff8e1", fg: "#b78103" };
  }
  return { bg: "#f5f5f5", fg: "var(--color-text-muted)" };
}

export function sortAttestations(list: TrustAttestation[]): TrustAttestation[] {
  return [...list].sort((a, b) => {
    const ia = CLAIM_ORDER.indexOf(a.claim_type as ClaimType);
    const ib = CLAIM_ORDER.indexOf(b.claim_type as ClaimType);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

export function parseScope(scope: unknown): string[] {
  if (Array.isArray(scope)) return scope.map(String);
  if (typeof scope === "string") {
    try {
      const parsed = JSON.parse(scope);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return scope ? [scope] : [];
    }
  }
  return [];
}

export function AttestationCard({
  att,
  claimLabel,
  statusLabel,
  evidenceLabel,
  confidenceHint,
  evidencePrefix,
  issuedPrefix,
  signedLabel,
  signatureOk,
}: {
  att: TrustAttestation;
  claimLabel: string;
  statusLabel: string;
  evidenceLabel: string;
  confidenceHint: string;
  evidencePrefix: string;
  issuedPrefix: string;
  signedLabel: string;
  signatureOk?: boolean | null;
}) {
  const tone = statusTone(att.verification_status);
  const issued = att.issued_at
    ? new Date(att.issued_at).toLocaleDateString()
    : "—";

  return (
    <article
      className="rounded-lg p-4"
      style={{
        backgroundColor: "var(--color-bg-card)",
        boxShadow: "var(--shadow-sm)",
        border: "1px solid #f0f0f0",
      }}
    >
      <div className="flex items-start justify-between gap-3 flex-wrap mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <h3
            className="text-sm font-semibold m-0"
            style={{ color: "var(--color-text-primary)" }}
          >
            {claimLabel}
          </h3>
          <span
            className="text-xs px-2 py-0.5 rounded"
            style={{ backgroundColor: tone.bg, color: tone.fg }}
          >
            {statusLabel}
          </span>
          {signatureOk === true && (
            <span
              className="text-xs px-2 py-0.5 rounded"
              style={{ backgroundColor: "#e8f5e9", color: "var(--color-success)" }}
            >
              {signedLabel}
            </span>
          )}
          {signatureOk === false && (
            <span
              className="text-xs px-2 py-0.5 rounded"
              style={{ backgroundColor: "#ffebee", color: "var(--color-danger)" }}
            >
              —
            </span>
          )}
        </div>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {confidenceHint}
        </span>
      </div>
      <p
        className="text-sm leading-relaxed m-0 mb-3"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {att.claim_statement}
      </p>
      <div
        className="flex flex-wrap gap-x-4 gap-y-1 text-xs"
        style={{ color: "var(--color-text-muted)" }}
      >
        <span>
          {evidencePrefix}
          {evidenceLabel}
        </span>
        <span>
          {issuedPrefix}
          {issued}
        </span>
        {att.signature && signatureOk == null ? <span>{signedLabel}</span> : null}
      </div>
    </article>
  );
}
