/**
 * TierGatePanel — shown when the current tier cannot access a feature.
 */
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Tier } from "@looma/shared-core";

export interface TierGatePanelProps {
  title: string;
  description: string;
  /** Minimum tier required (used for badge label). */
  minTier?: Tier;
}

function tierKey(tier: Tier): string {
  if (tier === "supporter") return "tier.supporter";
  if (tier === "enterprise") return "tier.pro";
  if (tier === "pro") return "tier.pro";
  return "tier.free";
}

export default function TierGatePanel({
  title,
  description,
  minTier = "supporter",
}: TierGatePanelProps) {
  const { t } = useTranslation();

  return (
    <div className="max-w-xl">
      <h1
        className="text-2xl font-bold mb-4"
        style={{ color: "var(--color-text-primary)" }}
      >
        {title}
      </h1>
      <div
        className="rounded-xl p-6"
        style={{
          backgroundColor: "var(--color-bg-card)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <p
          className="text-xs mb-3 uppercase tracking-wide"
          style={{ color: "var(--color-text-muted)" }}
        >
          {t("tier.requires", { tier: t(tierKey(minTier)) })}
        </p>
        <p
          className="text-sm mb-5 leading-relaxed"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {description}
        </p>
        <Link
          to="/pricing"
          className="inline-block px-4 py-2 rounded-lg text-sm text-white no-underline"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          {t("tier.viewUpgrade")}
        </Link>
      </div>
    </div>
  );
}
