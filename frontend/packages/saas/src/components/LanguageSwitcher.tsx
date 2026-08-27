import { useTranslation } from "react-i18next";
import { setLanguage } from "../i18n";

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const current = i18n.language.startsWith("zh") ? "zh" : "en";

  return (
    <div
      className="inline-flex rounded-md border border-gray-200 overflow-hidden text-xs"
      role="group"
      aria-label={t("lang.switchAria")}
    >
      <button
        type="button"
        className={`px-2 py-1 border-none cursor-pointer ${current === "en" ? "text-white" : "bg-transparent"}`}
        style={current === "en" ? { backgroundColor: "var(--color-primary)" } : undefined}
        onClick={() => setLanguage("en")}
      >
        {t("lang.en")}
      </button>
      <button
        type="button"
        className={`px-2 py-1 border-none cursor-pointer ${current === "zh" ? "text-white" : "bg-transparent"}`}
        style={current === "zh" ? { backgroundColor: "var(--color-primary)" } : undefined}
        onClick={() => setLanguage("zh")}
      >
        {t("lang.zh")}
      </button>
    </div>
  );
}
