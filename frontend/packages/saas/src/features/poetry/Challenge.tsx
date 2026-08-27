/**
 * Xin-Da-Ya weekly translation challenge — overseas MVP submit page.
 * Owner: Jason
 *
 * Flow: load current round → show poem → submit English translation (1 per week).
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  API_ROUTES,
  ApiError,
  type ChallengeCurrentResponse,
  type ChallengeEntry,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { IS_OVERSEAS } from "../../config/region";

function errMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const body = e.body as { message?: string } | undefined;
    return body?.message || e.message || fallback;
  }
  if (e && typeof e === "object" && "message" in e) {
    return String((e as { message?: string }).message) || fallback;
  }
  return fallback;
}

export default function Challenge() {
  const { t } = useTranslation();
  const api = useCallback(() => createSaasApiClient(), []);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [data, setData] = useState<ChallengeCurrentResponse | null>(null);

  const [translation, setTranslation] = useState("");
  const [note, setNote] = useState("");
  const [licenseAccepted, setLicenseAccepted] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api().get<ChallengeCurrentResponse>(
        API_ROUTES.POETRY_CHALLENGE_CURRENT,
      );
      setData(res);
      if (res.my_entry) {
        setTranslation(res.my_entry.translation || "");
        setNote(res.my_entry.note || "");
        setLicenseAccepted(Boolean(res.my_entry.license_accepted));
      }
    } catch (e: unknown) {
      setError(errMessage(e, t("challenge.loadFailed")));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [api, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSubmit = async () => {
    setSuccess(null);
    setError(null);
    if (!licenseAccepted) {
      setError(t("challenge.licenseRequired"));
      return;
    }
    if (translation.trim().length < 8) {
      setError(t("challenge.translationTooShort"));
      return;
    }
    setSubmitting(true);
    try {
      const res = await api().post<{ entry: ChallengeEntry; round_id: number }>(
        API_ROUTES.POETRY_CHALLENGE_ENTRIES,
        {
          round_id: data?.round?.id,
          translation: translation.trim(),
          note: note.trim(),
          license_accepted: true,
        },
      );
      setSuccess(
        data?.my_entry
          ? t("challenge.updated")
          : t("challenge.submitted"),
      );
      setData((prev) =>
        prev
          ? { ...prev, my_entry: res.entry }
          : prev,
      );
    } catch (e: unknown) {
      setError(errMessage(e, t("challenge.submitFailed")));
    } finally {
      setSubmitting(false);
    }
  };

  const poem = data?.poem;
  const round = data?.round;
  const closed = round?.status === "closed";
  const endsLabel = round?.ends_at
    ? new Date(round.ends_at).toLocaleString()
    : "—";

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <p
            className="text-xs uppercase tracking-widest mb-1"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {t("challenge.eyebrow")}
          </p>
          <h1
            className="text-2xl font-bold"
            style={{ color: "var(--color-text-primary)" }}
          >
            {t("challenge.title")}
          </h1>
          <p
            className="text-sm mt-2"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {t("challenge.subtitle")}
          </p>
        </div>
        <Link
          to="/poetry"
          className="text-sm shrink-0 no-underline"
          style={{ color: "var(--color-primary)" }}
        >
          {t("challenge.backToLibrary")}
        </Link>
      </div>

      {!IS_OVERSEAS && (
        <div
          className="mb-4 p-3 rounded text-sm"
          style={{
            backgroundColor: "var(--color-bg-surface)",
            color: "var(--color-text-secondary)",
          }}
        >
          {t("challenge.overseasHint")}
        </div>
      )}

      {loading && (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {t("challenge.loading")}
        </p>
      )}

      {!loading && error && !poem && (
        <div
          className="p-4 rounded-lg text-sm"
          style={{
            backgroundColor: "var(--color-bg-surface)",
            borderLeft: "3px solid var(--color-warning)",
            color: "var(--color-text-primary)",
          }}
        >
          <p className="font-medium mb-1">{t("challenge.unavailable")}</p>
          <p style={{ color: "var(--color-text-secondary)" }}>{error}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="mt-3 px-3 py-1.5 text-xs rounded border-none cursor-pointer text-white"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            {t("challenge.retry")}
          </button>
        </div>
      )}

      {!loading && poem && round && (
        <>
          <section
            className="rounded-lg p-5 mb-6"
            style={{
              backgroundColor: "var(--color-bg-card)",
              boxShadow: "var(--shadow-sm)",
              borderLeft: "3px solid var(--color-primary)",
            }}
          >
            <div className="flex items-baseline justify-between gap-3 mb-3">
              <h2
                className="text-lg font-bold"
                style={{ color: "var(--color-text-primary)" }}
              >
                {poem.title}
              </h2>
              <span
                className="text-xs shrink-0"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {round.week_key}
              </span>
            </div>
            <p
              className="text-sm mb-4"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {poem.dynasty} · {poem.author}
            </p>
            <pre
              className="whitespace-pre-wrap font-serif text-base leading-relaxed m-0"
              style={{ color: "var(--color-text-primary)" }}
            >
              {poem.content}
            </pre>
            <p
              className="text-xs mt-4"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {t("challenge.deadline", { when: endsLabel })}
              {closed ? ` · ${t("challenge.closed")}` : ""}
            </p>
          </section>

          <section className="space-y-4">
            <label className="block">
              <span
                className="text-sm font-medium block mb-1.5"
                style={{ color: "var(--color-text-primary)" }}
              >
                {t("challenge.translationLabel")}
              </span>
              <textarea
                value={translation}
                onChange={(e) => setTranslation(e.target.value)}
                disabled={closed || submitting}
                rows={6}
                placeholder={t("challenge.translationPlaceholder")}
                className="w-full px-3 py-2 text-sm rounded-lg border outline-none resize-y"
                style={{
                  borderColor: "var(--color-border)",
                  color: "var(--color-text-primary)",
                  backgroundColor: "var(--color-bg-card)",
                }}
              />
            </label>

            <label className="block">
              <span
                className="text-sm font-medium block mb-1.5"
                style={{ color: "var(--color-text-primary)" }}
              >
                {t("challenge.noteLabel")}
              </span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={closed || submitting}
                rows={2}
                maxLength={200}
                placeholder={t("challenge.notePlaceholder")}
                className="w-full px-3 py-2 text-sm rounded-lg border outline-none resize-y"
                style={{
                  borderColor: "var(--color-border)",
                  color: "var(--color-text-primary)",
                  backgroundColor: "var(--color-bg-card)",
                }}
              />
            </label>

            <label className="flex items-start gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={licenseAccepted}
                onChange={(e) => setLicenseAccepted(e.target.checked)}
                disabled={closed || submitting}
                className="mt-1"
              />
              <span style={{ color: "var(--color-text-secondary)" }}>
                {t("challenge.license")}
              </span>
            </label>

            {error && (
              <p className="text-sm" style={{ color: "var(--color-danger)" }}>
                {error}
              </p>
            )}
            {success && (
              <p className="text-sm" style={{ color: "var(--color-success)" }}>
                {success}
              </p>
            )}

            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={closed || submitting}
              className="px-5 py-2.5 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-40"
              style={{ backgroundColor: "var(--color-primary)" }}
            >
              {submitting
                ? t("challenge.submitting")
                : data?.my_entry
                  ? t("challenge.update")
                  : t("challenge.submit")}
            </button>
          </section>
        </>
      )}
    </div>
  );
}
