import { useTranslation } from "react-i18next";
import { LegalDocument } from "../components/LegalDocument";
import { usePageMeta, LegalSection } from "../lib/i18n-helpers";

export function TermsPage() {
  const { t } = useTranslation();
  usePageMeta("meta.terms");
  const sections = t("legal.terms.sections", { returnObjects: true }) as LegalSection[];

  return (
    <LegalDocument
      title={t("legal.terms.title")}
      introKey="legal.terms.intro"
      sections={sections}
      contactLabel={t("legal.contactTerms")}
    />
  );
}
