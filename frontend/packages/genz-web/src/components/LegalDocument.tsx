import { Trans, useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { SITE_CONFIG } from "../config/site";
import { HtmlText, LegalSection } from "../lib/i18n-helpers";

type LegalDocumentProps = {
  title: string;
  introKey: string;
  sections: LegalSection[];
  contactLabel: string;
  introValues?: Record<string, string>;
};

function renderListItem(item: string, index: number) {
  if (item.includes("<1>")) {
    return (
      <li key={index}>
        <Trans
          defaults={item}
          components={{
            1: item.includes("{{email}}") ? (
              <a href={`mailto:${SITE_CONFIG.supportEmail}`} />
            ) : item.includes("定价") || item.toLowerCase().includes("pricing") ? (
              <Link to="/pricing" />
            ) : item.includes("Refund") || item.includes("退款") ? (
              <Link to="/legal/refund" />
            ) : (
              <a href={SITE_CONFIG.siteUrl} />
            ),
          }}
          values={{ email: SITE_CONFIG.supportEmail }}
        />
      </li>
    );
  }
  return (
    <li key={index}>
      <HtmlText html={item} />
    </li>
  );
}

function renderParagraph(text: string, index: number) {
  if (text.includes("<1>")) {
    return (
      <p key={index}>
        <Trans
          defaults={text}
          components={{
            1: text.includes("{{email}}") ? (
              <a href={`mailto:${SITE_CONFIG.supportEmail}`} />
            ) : text.includes("Refund") || text.includes("退款") ? (
              <Link to="/legal/refund" />
            ) : (
              <Link to="/pricing" />
            ),
          }}
          values={{ email: SITE_CONFIG.supportEmail, entity: SITE_CONFIG.legalEntityName }}
        />
      </p>
    );
  }
  if (text.includes("{{entity}}")) {
    return (
      <p key={index}>
        {text.replace(/\{\{entity\}\}/g, SITE_CONFIG.legalEntityName)}
      </p>
    );
  }
  return (
    <p key={index}>
      <HtmlText html={text} />
    </p>
  );
}

export function LegalDocument({
  title,
  introKey,
  sections,
  contactLabel,
  introValues,
}: LegalDocumentProps) {
  const { t } = useTranslation();

  return (
    <main className="legal-doc">
      <div className="container">
        <h1>{title}</h1>
        <p className="updated">{t("legal.updated")}</p>
        <p>
          <Trans
            i18nKey={introKey}
            components={{
              1: <a href={SITE_CONFIG.siteUrl} />,
              2: <a href={SITE_CONFIG.apiBase} />,
            }}
            values={{
              entity: SITE_CONFIG.legalEntityName,
              ...introValues,
            }}
          />
        </p>
        {sections.map((section, idx) => (
          <section key={idx}>
            <h2>{section.title}</h2>
            {section.paragraphs?.map((p, i) => renderParagraph(p, i))}
            {section.list && <ul>{section.list.map(renderListItem)}</ul>}
            {section.afterList?.map((p, i) => renderParagraph(p, i + 1000))}
          </section>
        ))}
        <p>
          {contactLabel}{" "}
          <a href={`mailto:${SITE_CONFIG.supportEmail}`}>{SITE_CONFIG.supportEmail}</a>
        </p>
      </div>
    </main>
  );
}
