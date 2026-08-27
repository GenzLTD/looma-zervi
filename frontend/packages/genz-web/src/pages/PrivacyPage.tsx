import { useTranslation } from "react-i18next";
import { LegalDocument } from "../components/LegalDocument";
import { usePageMeta, LegalSection } from "../lib/i18n-helpers";

export function PrivacyPage() {
  const { t } = useTranslation();
  usePageMeta("meta.privacy");
  const sections = t("legal.privacy.sections", { returnObjects: true }) as LegalSection[];

  return (
    <LegalDocument
      title={t("legal.privacy.title")}
      introKey="legal.privacy.intro"
      sections={sections}
      contactLabel={t("legal.contactPrivacy")}
    />
  );
}
