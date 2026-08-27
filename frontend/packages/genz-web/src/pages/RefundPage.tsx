import { useTranslation } from "react-i18next";
import { LegalDocument } from "../components/LegalDocument";
import { usePageMeta, LegalSection } from "../lib/i18n-helpers";

export function RefundPage() {
  const { t } = useTranslation();
  usePageMeta("meta.refund");
  const sections = t("legal.refund.sections", { returnObjects: true }) as LegalSection[];

  return (
    <LegalDocument
      title={t("legal.refund.title")}
      introKey="legal.refund.intro"
      sections={sections}
      contactLabel={t("legal.contactBilling")}
    />
  );
}
