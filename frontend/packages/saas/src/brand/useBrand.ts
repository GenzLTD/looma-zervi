import { useTranslation } from "react-i18next";

/** Locale-aware brand name/slogan — overrides shared-core BRAND_SAAS for overseas. */
export function useBrand() {
  const { t } = useTranslation();
  return {
    name: t("brand.name"),
    slogan: t("brand.slogan"),
  };
}
