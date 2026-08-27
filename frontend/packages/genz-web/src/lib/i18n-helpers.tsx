import { useEffect } from "react";
import { useTranslation } from "react-i18next";

export function usePageMeta(metaKey: string) {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    document.title = t(`${metaKey}.title`);
    const desc = document.querySelector('meta[name="description"]');
    if (desc) {
      desc.setAttribute("content", t(`${metaKey}.description`));
    }
    document.documentElement.lang = i18n.language === "zh" ? "zh-Hans" : "en";
  }, [t, i18n.language, metaKey]);
}

export type LegalSection = {
  title: string;
  paragraphs?: string[];
  list?: string[];
  afterList?: string[];
};

export function HtmlText({ html }: { html: string }) {
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}
