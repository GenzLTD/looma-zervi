import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { SITE_CONFIG } from "../config/site";
import { usePageMeta } from "../lib/i18n-helpers";

export function HomePage() {
  const { t } = useTranslation();
  usePageMeta("meta.home");

  const summaryItems = t("home.summaryItems", { returnObjects: true }) as string[];

  return (
    <main>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <div className="eyebrow">{t("home.eyebrow")}</div>
            <h1>{t("home.title")}</h1>
            <p className="lead">{t("home.lead")}</p>
            <div className="btn-row">
              <a className="btn btn-primary" href={SITE_CONFIG.appRegisterUrl}>
                {t("home.ctaRegister")}
              </a>
              <Link className="btn btn-secondary" to="/pricing">
                {t("home.ctaPricing")}
              </Link>
              <a className="btn btn-secondary" href={`mailto:${SITE_CONFIG.supportEmail}`}>
                {t("home.ctaSupport")}
              </a>
            </div>
          </div>
          <aside className="hero-card" aria-label={t("home.summaryTitle")}>
            <h2>{t("home.summaryTitle")}</h2>
            <ul>
              {summaryItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </aside>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <h2>{t("home.featuresTitle")}</h2>
          <p className="section-lead">{t("home.featuresLead")}</p>
          <div className="feature-grid">
            {(["coaching", "resume", "matching", "plans"] as const).map((key) => (
              <article className="card" key={key}>
                <h3>{t(`home.features.${key}.title`)}</h3>
                <p>{t(`home.features.${key}.body`)}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <h2>{t("home.billingTitle")}</h2>
          <p className="section-lead">{t("home.billingLead")}</p>
          <div className="contact-box">
            <p>
              <strong>{t("site.support")}:</strong>{" "}
              <a href={`mailto:${SITE_CONFIG.supportEmail}`}>{SITE_CONFIG.supportEmail}</a>
            </p>
            <p>
              <strong>{t("site.api")}:</strong>{" "}
              <a href={SITE_CONFIG.apiBase} rel="noopener noreferrer">
                {SITE_CONFIG.apiBase.replace("https://", "")}
              </a>
            </p>
            <p className="status-note">{t("home.paymentsNote")}</p>
          </div>
        </div>
      </section>
    </main>
  );
}
