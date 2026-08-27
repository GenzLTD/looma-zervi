import { Link, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { SITE_CONFIG } from "../config/site";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function SiteHeader() {
  const { t } = useTranslation();

  const navClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? "active" : undefined;

  return (
    <header className="site-header">
      <div className="container inner">
        <Link className="brand" to="/">
          <strong>{t("site.brand")}</strong>
          <span>{t("site.tagline")}</span>
        </Link>
        <nav className="site-nav" aria-label={t("site.navAria")}>
          <NavLink to="/" end className={navClass}>
            {t("site.nav.home")}
          </NavLink>
          <NavLink to="/pricing" className={navClass}>
            {t("site.nav.pricing")}
          </NavLink>
          <NavLink to="/legal/privacy" className={navClass}>
            {t("site.nav.privacy")}
          </NavLink>
          <NavLink to="/legal/terms" className={navClass}>
            {t("site.nav.terms")}
          </NavLink>
          <NavLink to="/legal/refund" className={navClass}>
            {t("site.nav.refund")}
          </NavLink>
          <LanguageSwitcher />
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  const { t } = useTranslation();
  const year = new Date().getFullYear();
  const email = SITE_CONFIG.supportEmail;

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <strong>
              {SITE_CONFIG.brandName} · {SITE_CONFIG.productName}
            </strong>
            <br />
            {t("site.tagline")}
            <p>
              © {year} {SITE_CONFIG.legalEntityName}. {t("site.footer.rights")}
            </p>
          </div>
          <div className="footer-links">
            <Link to="/pricing">{t("site.nav.pricing")}</Link>
            <Link to="/legal/privacy">{t("site.nav.privacy")}</Link>
            <Link to="/legal/terms">{t("site.nav.terms")}</Link>
            <Link to="/legal/refund">{t("site.nav.refund")}</Link>
            <a href={`mailto:${email}`}>{email}</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
