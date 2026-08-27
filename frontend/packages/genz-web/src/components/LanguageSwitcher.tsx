import { useTranslation } from "react-i18next";
import { setLanguage } from "../i18n";

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const current = i18n.language.startsWith("zh") ? "zh" : "en";

  return (
    <div className="lang-switch" role="group" aria-label={t("site.lang.switchAria")}>
      <button
        type="button"
        className={current === "en" ? "active" : ""}
        onClick={() => setLanguage("en")}
      >
        {t("site.lang.en")}
      </button>
      <button
        type="button"
        className={current === "zh" ? "active" : ""}
        onClick={() => setLanguage("zh")}
      >
        {t("site.lang.zh")}
      </button>
    </div>
  );
}
