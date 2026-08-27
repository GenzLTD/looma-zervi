/**
 * Single candidate detail — HR view of PlanetX personality profile.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  createEnterpriseApi,
  hasMinTier,
  type Candidate,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useSaasAuthStore } from "../auth/authStore";
import TierGatePanel from "../../brand/components/TierGatePanel";
import TimelineL1Card from "./TimelineL1Card";

export default function CandidateDetail() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const { user } = useSaasAuthStore();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tierBlocked, setTierBlocked] = useState(false);

  const canUseCandidates = hasMinTier(user?.tier, "supporter");

  useEffect(() => {
    if (!id) return;
    if (!canUseCandidates) {
      setTierBlocked(true);
      return;
    }
    const client = createSaasApiClient();
    createEnterpriseApi(client)
      .getCandidate(id)
      .then(setCandidate)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setTierBlocked(true);
        } else {
          setError(t("candidates.loadFailed"));
        }
      });
  }, [id, canUseCandidates, t]);

  if (!canUseCandidates || tierBlocked) {
    return (
      <TierGatePanel
        title={t("candidates.title")}
        description={t("candidates.tierRequired")}
        minTier="supporter"
      />
    );
  }

  if (error) {
    return (
      <div>
        <p style={{ color: "var(--color-text-muted)" }}>{error}</p>
        <Link to="/candidates" style={{ color: "var(--color-primary)" }}>
          {t("candidates.backToList")}
        </Link>
      </div>
    );
  }

  if (!candidate) {
    return <p style={{ color: "var(--color-text-muted)" }}>{t("candidates.loadingDetail")}</p>;
  }

  const profile = candidate.profile_data as {
    personality_type?: string;
    personality_detail?: { name?: string; emoji?: string; tagline?: string; desc?: string; traits?: string[] };
    xp?: number;
    level?: number;
  } | undefined;

  const detail = profile?.personality_detail;
  const emoji = detail?.emoji ?? "🪐";
  const name = detail?.name ?? profile?.personality_type ?? "未知类型";

  return (
    <div className="max-w-2xl">
      <Link to="/candidates" className="text-sm mb-4 inline-block" style={{ color: "var(--color-primary)" }}>
        {t("candidates.backToList")}
      </Link>

      <div
        className="rounded-2xl p-8 mb-6"
        style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-md)" }}
      >
        <div className="text-center mb-6">
          <div className="text-5xl mb-3">{emoji}</div>
          <h1 className="text-xl font-bold" style={{ color: "var(--color-text-primary)" }}>
            {candidate.name}
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-muted)" }}>
            {name} · Lv.{profile?.level ?? 1}
          </p>
          {candidate.email && (
            <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>{candidate.email}</p>
          )}
        </div>

        {detail?.tagline && (
          <p className="text-center italic mb-4 text-sm" style={{ color: "var(--color-primary)" }}>
            「{detail.tagline}」
          </p>
        )}

        {detail?.traits && detail.traits.length > 0 && (
          <div className="flex flex-wrap justify-center gap-2 mb-4">
            {detail.traits.map((t) => (
              <span
                key={t}
                className="px-3 py-1 rounded-full text-xs"
                style={{ backgroundColor: "var(--color-bg-surface)" }}
              >
                {t}
              </span>
            ))}
          </div>
        )}

        {detail?.desc && (
          <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
            {detail.desc}
          </p>
        )}
      </div>

      <TimelineL1Card summary={candidate.timeline_l1} />

      {!hasMinTier(user?.tier, "pro") && (
        <Link
          to="/pricing"
          className="inline-block px-5 py-2 rounded-lg text-sm text-white no-underline"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          {t("candidates.upgradeForMore")}
        </Link>
      )}
    </div>
  );
}
