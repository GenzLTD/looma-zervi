import { useCallback, useEffect, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { SITE_CONFIG } from "../config/site";
import { usePageMeta } from "../lib/i18n-helpers";

type PlanTier = "free" | "supporter" | "pro";

export type PricingPlan = {
  tier: PlanTier | string;
  name: string;
  price_monthly: number;
  currency: string;
  features: string[];
  upgradable?: boolean;
};

const PROVIDER_ORDER = ["stripe", "paypal", "airwallex"] as const;

const FALLBACK_PLANS: PricingPlan[] = [
  { tier: "free", name: "Free", price_monthly: 0, currency: "USD", features: [], upgradable: false },
  { tier: "supporter", name: "Supporter", price_monthly: 1.99, currency: "USD", features: [], upgradable: true },
  { tier: "pro", name: "Pro", price_monthly: 5.99, currency: "USD", features: [], upgradable: true },
];

function formatPrice(price: number) {
  if (!price) return "$0";
  return `$${price}`;
}

export function PricingPage() {
  const { t } = useTranslation();
  usePageMeta("meta.pricing");

  const [plans, setPlans] = useState<PricingPlan[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "api" | "fallback">("loading");
  const [checkoutState, setCheckoutState] = useState<Record<string, "idle" | "loading" | "error">>({});

  const localizePlan = useCallback(
    (plan: PricingPlan): PricingPlan => {
      const tier = plan.tier as PlanTier;
      const localizedFeatures = t(`pricing.plans.${tier}.features`, {
        returnObjects: true,
        defaultValue: plan.features,
      }) as string[];
      return {
        ...plan,
        name: t(`pricing.plans.${tier}.name`, { defaultValue: plan.name }),
        features: Array.isArray(localizedFeatures) ? localizedFeatures : plan.features,
      };
    },
    [t],
  );

  useEffect(() => {
    const apiBase = SITE_CONFIG.apiBase;

    fetch(`${apiBase}/v1/payment/providers?region=US`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setProviders(data.providers || []))
      .catch(() => setProviders([]))
      .finally(() => {
        fetch(`${apiBase}/v1/payment/plans?region=US`)
          .then((res) => (res.ok ? res.json() : Promise.reject()))
          .then((data) => {
            const list = (data.plans || []).filter((p: PricingPlan) => p.tier !== "enterprise");
            if (!list.length) throw new Error("empty");
            setPlans(list.map(localizePlan));
            setStatus("api");
          })
          .catch(() => {
            setPlans(FALLBACK_PLANS.map(localizePlan));
            setStatus("fallback");
          });
      });
  }, [localizePlan]);

  const handleCheckout = async (provider: string, tier: string) => {
    setCheckoutState((s) => ({ ...s, [tier]: "loading" }));
    try {
      const res = await fetch(`${SITE_CONFIG.apiBase}/v1/payment/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          tier,
          mode: "payment",
          success_url: `${window.location.origin}/pricing?status=success&session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/pricing?status=cancel`,
        }),
      });
      if (!res.ok) {
        // 401 = unauthenticated → redirect to SaaS register
        if (res.status === 401) {
          window.location.href = SITE_CONFIG.appRegisterUrl;
          return;
        }
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || "Checkout failed");
      }
      const data = await res.json();
      if (!data.checkout_url) throw new Error("No checkout URL");
      window.location.href = data.checkout_url;
    } catch (e) {
      setCheckoutState((s) => ({ ...s, [tier]: "error" }));
      const message = e instanceof Error ? e.message : String(e);
      alert(t("pricing.paymentError", { message, email: SITE_CONFIG.supportEmail }));
    }
  };

  const providerOptions = PROVIDER_ORDER.filter(
    (p) => providers.length === 0 || providers.includes(p),
  );

  const statusText =
    status === "loading"
      ? t("pricing.loading")
      : status === "api"
        ? t("pricing.statusApi") +
          (providers.length
            ? " " + t("pricing.statusProviders", {
                list: providers.map((p) => t(`pricing.providers.${p}`, { defaultValue: p })).join(", "),
              })
            : "")
        : t("pricing.statusFallback");

  return (
    <main className="section">
      <div className="container">
        <h1>{t("pricing.title")}</h1>
        <p className="section-lead">{t("pricing.lead")}</p>
        <p className={`pricing-status ${status === "api" ? "ok" : ""}`}>{statusText}</p>

        <div className="pricing-grid" aria-live="polite">
          {plans.map((plan) => {
            const popular = plan.tier === "pro";
            const tierState = checkoutState[plan.tier] || "idle";
            return (
              <article className={`card${popular ? " popular" : ""}`} key={plan.tier}>
                {popular && <div className="badge">{t("pricing.mostPopular")}</div>}
                <h3>{plan.name}</h3>
                <div className="price">
                  {formatPrice(plan.price_monthly)}
                  <span>{t("pricing.perMonth")}</span>
                </div>
                <p>{t("pricing.billedMonthly")}</p>
                <ul>
                  {plan.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                {plan.tier !== "free" && (
                  <div className="provider-select">
                    <label htmlFor={`provider-${plan.tier}`}>{t("pricing.paymentMethod")}</label>
                    <select id={`provider-${plan.tier}`} className="provider-dropdown" defaultValue={providerOptions[0]}>
                      {providerOptions.map((p) => (
                        <option key={p} value={p}>
                          {t(`pricing.providers.${p}`)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {plan.tier === "free" ? (
                  <a
                    className="btn btn-secondary"
                    href={SITE_CONFIG.appRegisterUrl}
                  >
                    {t("pricing.getStartedFree")}
                  </a>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={tierState === "loading"}
                    onClick={() => {
                      const sel = document.getElementById(`provider-${plan.tier}`) as HTMLSelectElement | null;
                      void handleCheckout(sel?.value || "stripe", plan.tier);
                    }}
                  >
                    {tierState === "loading"
                      ? t("pricing.redirecting")
                      : tierState === "error"
                        ? t("pricing.tryAgain")
                        : t("pricing.subscribe")}
                  </button>
                )}
              </article>
            );
          })}
        </div>

        <div className="contact-box" style={{ marginTop: "2rem" }}>
          <h3 style={{ margin: "0 0 0.5rem", color: "var(--text)" }}>{t("pricing.enterpriseTitle")}</h3>
          <p style={{ margin: 0 }}>
            <Trans
              i18nKey="pricing.enterpriseBody"
              values={{ email: SITE_CONFIG.supportEmail }}
              components={{ 1: <a href={`mailto:${SITE_CONFIG.supportEmail}`} /> }}
            />
          </p>
        </div>

        <p className="status-note">
          <Trans i18nKey="pricing.footnote" components={{ 1: <Link to="/legal/refund" /> }} />
        </p>
      </div>
    </main>
  );
}
