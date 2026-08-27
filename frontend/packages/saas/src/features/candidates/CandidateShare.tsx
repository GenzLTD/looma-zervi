/**
 * Public candidate profile view — HR opens share link from PlanetX.
 */
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  BRAND_SAAS,
  createReferralApi,
  type ProfileShareView,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { parsePersonalityDetail } from "./personalityDetail";
import TimelineL1Card from "./TimelineL1Card";
import { MicroFeedbackBar } from "../../brand/components/MicroFeedbackBar";
import { MICRO_FEEDBACK_CONTEXT } from "@looma/shared-core";

export default function CandidateShare() {
  const { code } = useParams<{ code: string }>();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<ProfileShareView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!code) {
      setError("无效的分享链接");
      setLoading(false);
      return;
    }
    const client = createSaasApiClient();
    const api = createReferralApi(client);
    api
      .profileView(code.toUpperCase())
      .then(setData)
      .catch(() => setError("分享码无效或该用户尚未完成测试"))
      .finally(() => setLoading(false));
  }, [code]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "var(--color-bg-page)" }}>
        <p style={{ color: "var(--color-text-muted)" }}>加载求职者画像…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-6" style={{ backgroundColor: "var(--color-bg-page)" }}>
        <p style={{ color: "var(--color-text-secondary)" }}>{error ?? "未找到画像"}</p>
        <Link to="/register" className="text-sm underline" style={{ color: "var(--color-primary)" }}>
          注册 {BRAND_SAAS.name} 开始试用
        </Link>
      </div>
    );
  }

  const p = parsePersonalityDetail(data);
  const registerUrl = `/register?from=share&code=${encodeURIComponent(code ?? "")}${searchParams.get("ref") ? `&ref=${searchParams.get("ref")}` : ""}`;

  return (
    <div className="min-h-screen py-10 px-4" style={{ backgroundColor: "var(--color-bg-page)" }}>
      <div className="max-w-lg mx-auto">
        <p className="text-center text-xs mb-2" style={{ color: "var(--color-text-muted)" }}>
          {BRAND_SAAS.name} · 求职者画像
        </p>

        <div
          className="rounded-2xl p-8 text-center mb-6"
          style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-md)" }}
        >
          <div className="text-6xl mb-4">{p.emoji ?? "🪐"}</div>
          <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--color-text-primary)" }}>
            {p.name ?? data.personality_type}
          </h1>
          <p className="text-sm mb-4" style={{ color: "var(--color-text-secondary)" }}>
            {data.user_display} · Lv.{data.level}
          </p>
          {p.tagline && (
            <p className="text-sm italic mb-4" style={{ color: "var(--color-primary)" }}>
              「{p.tagline}」
            </p>
          )}
          {p.traits && p.traits.length > 0 && (
            <div className="flex flex-wrap justify-center gap-2 mb-4">
              {p.traits.map((t) => (
                <span
                  key={t}
                  className="px-3 py-1 rounded-full text-xs"
                  style={{ backgroundColor: "var(--color-bg-surface)", color: "var(--color-text-secondary)" }}
                >
                  {t}
                </span>
              ))}
            </div>
          )}
          {p.desc && (
            <p className="text-sm leading-relaxed text-left" style={{ color: "var(--color-text-secondary)" }}>
              {p.desc}
            </p>
          )}
        </div>

        <TimelineL1Card summary={data.timeline_l1} />

        <div
          className="rounded-xl p-6 text-center"
          style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: "var(--color-text-primary)" }}>
            想查看更多候选人画像？
          </p>
          <p className="text-xs mb-4" style={{ color: "var(--color-text-muted)" }}>
            注册 {BRAND_SAAS.name}，内测期间免费体验 AI 招聘工作台
          </p>
          <Link
            to={registerUrl}
            className="inline-block px-6 py-2.5 rounded-lg text-sm font-medium text-white no-underline"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            免费试用 T-space →
          </Link>
        </div>

        <MicroFeedbackBar
          context={MICRO_FEEDBACK_CONTEXT.TSPACE_PROFILE_SHARE}
          question="这些信息够帮你做判断吗？"
          shareCode={code}
        />
      </div>
    </div>
  );
}
