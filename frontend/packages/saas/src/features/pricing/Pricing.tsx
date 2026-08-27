/**
 * Pricing Page — 套餐对比 + 支付（Stub / WeChat Pay）
 */
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  BRAND_SAAS,
  createAuthApi,
  createPaymentApi,
  createEnterpriseApi,
  CLOSED_LOOP_EVENTS,
  trackEvent,
  type PaymentPlan,
  type ContactSalesRequest,
  type WechatOrderResponse,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useSaasAuthStore } from "../auth/authStore";
import SaasModal from "../../brand/ui/SaasModal";
import { BILLING_REGION, IS_OVERSEAS } from "../../config/region";

interface PlanCard extends PaymentPlan {
  desc: string;
  highlight: boolean;
  badge?: string;
  actionLabel?: string;
}

const PLAN_META_CN: Record<string, Pick<PlanCard, "desc" | "highlight" | "badge" | "actionLabel">> = {
  free: {
    desc: "入门体验，探索 AI 招聘潜力",
    highlight: false,
    badge: "内测中",
  },
  supporter: {
    desc: "支持项目发展，解除主要配额限制",
    highlight: false,
    badge: "支持者",
    actionLabel: "成为支持者",
  },
  pro: {
    desc: "深度使用，释放 AI 全部能力",
    highlight: true,
    badge: "7 天试用",
    actionLabel: "开始 7 天试用",
  },
};

const PLAN_META_US: Record<string, Pick<PlanCard, "desc" | "highlight" | "badge" | "actionLabel">> = {
  free: {
    desc: "Explore AI career tools for free",
    highlight: false,
    badge: "Free",
  },
  supporter: {
    desc: "Unlock higher limits and support the project",
    highlight: false,
    badge: "Supporter",
    actionLabel: "Become Supporter",
  },
  pro: {
    desc: "Full AI power for serious career growth",
    highlight: true,
    badge: "7-day trial",
    actionLabel: "Start Pro trial",
  },
};

const PLAN_META = IS_OVERSEAS ? PLAN_META_US : PLAN_META_CN;

const ENTERPRISE_CARD: PlanCard = {
  tier: "enterprise",
  name: "企业版",
  price_monthly: 0,
  currency: "CNY",
  region: BILLING_REGION,
  plan_id: "enterprise_contact_cn",
  features: [
    "不限次数所有功能",
    "专属知识库训练",
    "批量简历处理",
    "API 接口对接",
    "7×24 专属技术支持",
  ],
  upgradable: false,
  desc: "为团队打造，定制化 AI 招聘方案",
  highlight: false,
  badge: "定制",
};

function formatPrice(plan: PaymentPlan): string {
  if (plan.tier === "enterprise") {
    return "联系我们";
  }
  if (plan.price_monthly === 0) {
    return plan.currency === "USD" ? "$0" : "¥0";
  }
  const symbol = plan.currency === "USD" ? "$" : "¥";
  return `${symbol}${plan.price_monthly}/月`;
}

export default function Pricing() {
  const { isAuthenticated, token, applySessionToken, fetchProfile } = useSaasAuthStore();
  const navigate = useNavigate();
  const [plans, setPlans] = useState<PlanCard[]>([]);
  const [stubMode, setStubMode] = useState(true);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [upgradingTier, setUpgradingTier] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [contactModalOpen, setContactModalOpen] = useState(false);
  const [contactSubmitting, setContactSubmitting] = useState(false);
  const [contactForm, setContactForm] = useState<ContactSalesRequest>({
    company_name: "",
    contact_name: "",
    contact_email: "",
    contact_phone: "",
    scale: "",
    message: "",
  });

  // WeChat Pay 状态
  const [wechatOrder, setWechatOrder] = useState<WechatOrderResponse | null>(null);
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [pollingOrder, setPollingOrder] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const client = createSaasApiClient();
        const resp = await createPaymentApi(client).plans(BILLING_REGION);
        if (cancelled) return;
        const cards: PlanCard[] = resp.plans.map((plan) => ({
          ...plan,
          ...PLAN_META[plan.tier],
        }));
        setPlans(IS_OVERSEAS ? cards : [...cards, ENTERPRISE_CARD]);
        setStubMode(resp.stub_mode ?? true);
      } catch {
        if (!cancelled) {
          setMessage("无法加载套餐价格，请稍后重试");
        }
      } finally {
        if (!cancelled) {
          setLoadingPlans(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleUpgrade = async (tier: "supporter" | "pro") => {
    if (!isAuthenticated || !token) {
      navigate("/register?from=pricing");
      return;
    }

    setUpgradingTier(tier);
    setMessage(null);
    trackEvent(CLOSED_LOOP_EVENTS.TRIAL_CLICKED);

    try {
      const client = createSaasApiClient();

      if (stubMode) {
        const resp = await createPaymentApi(client).upgrade(tier);
        if (resp.access_token) {
          await applySessionToken(resp.access_token);
        } else {
          const refreshed = await createAuthApi(client).refresh();
          await applySessionToken(refreshed.access_token);
        }
        const label = tier === "supporter"
          ? (IS_OVERSEAS ? "Supporter" : "支持者版")
          : (IS_OVERSEAS ? "Pro trial" : "Pro 试用");
        setMessage(
          IS_OVERSEAS
            ? `Activated ${label} (stub mode, no real payment)`
            : `已开通 ${label}（内测 Stub，无需真实支付）`,
        );
      } else if (IS_OVERSEAS) {
        const checkout = await createPaymentApi(client).checkout({
          provider: "stripe",
          tier,
          mode: "payment",
          success_url: `${window.location.origin}/pricing?status=success`,
          cancel_url: `${window.location.origin}/pricing?status=cancel`,
        });
        window.location.href = checkout.checkout_url;
      } else {
        const orderResp = await createPaymentApi(client).wechatOrder({
          tier,
          trade_type: "NATIVE", // PC Web 扫码支付
        });
        setWechatOrder(orderResp);
        setPaymentModalOpen(true);

        // 启动轮询检查支付状态
        pollPaymentStatus(orderResp.out_trade_no);
      }
    } catch (err: any) {
      if (err?.status === 402) {
        setMessage(IS_OVERSEAS ? "Payment required. Contact support to enable checkout." : "此服务需要真实支付，请联系管理员开通");
      } else {
        setMessage(IS_OVERSEAS ? "Something went wrong. Please try again." : "操作失败，请稍后重试");
      }
    } finally {
      setUpgradingTier(null);
    }
  };

  /** 轮询支付状态（每 3 秒检查一次，最多 60 次 / 3 分钟） */
  const pollPaymentStatus = async (_outTradeNo: string) => {
    setPollingOrder(true);
    let attempts = 0;
    const maxAttempts = 60;

    const poll = async () => {
      try {
        const client = createSaasApiClient();
        const status = await createPaymentApi(client).status();
        if (status.tier !== "free" && status.status !== "inactive") {
          // 支付成功
          setPollingOrder(false);
          setPaymentModalOpen(false);
          setWechatOrder(null);
          await fetchProfile();
          setMessage(`已开通 ${status.plan.name}！`);
          return;
        }
      } catch {
        // 忽略轮询错误
      }

      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(poll, 3000);
      } else {
        setPollingOrder(false);
        setMessage("支付状态查询超时，如已完成支付请刷新页面");
      }
    };

    poll();
  };

  const handleContactSubmit = async () => {
    if (!contactForm.company_name.trim() || !contactForm.contact_name.trim() || !contactForm.contact_email.trim()) {
      setMessage("请填写公司名称、联系人和邮箱");
      return;
    }
    setContactSubmitting(true);
    setMessage(null);
    try {
      const client = createSaasApiClient();
      const resp = await createEnterpriseApi(client).contactSales(contactForm);
      setMessage(resp.message);
      setContactModalOpen(false);
      setContactForm({
        company_name: "",
        contact_name: "",
        contact_email: "",
        contact_phone: "",
        scale: "",
        message: "",
      });
    } catch {
        setMessage("提交失败，请稍后重试");
    } finally {
      setContactSubmitting(false);
    }
  };

  /** 关闭支付弹窗 */
  const handleClosePayment = () => {
    setPaymentModalOpen(false);
    setWechatOrder(null);
    setPollingOrder(false);
  };

  return (
    <div className="max-w-5xl mx-auto" style={{ paddingTop: "1rem" }}>
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold mb-3" style={{ color: "var(--color-text-primary)" }}>
          选择适合你的方案
        </h1>
        <p className="text-sm max-w-md mx-auto" style={{ color: "var(--color-text-secondary)", lineHeight: 1.8 }}>
          {BRAND_SAAS.slogan}
        </p>
      </div>

      {loadingPlans ? (
        <p className="text-center text-sm mb-10" style={{ color: "var(--color-text-muted)" }}>
          加载套餐中…
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-10">
          {plans.map((plan) => (
            <div
              key={plan.tier}
              className="rounded-xl p-6 flex flex-col relative transition-shadow hover:shadow-lg"
              style={{
                backgroundColor: "var(--color-bg-card)",
                boxShadow: plan.highlight ? "0 0 0 2px var(--color-primary), var(--shadow-md)" : "var(--shadow-sm)",
                transform: plan.highlight ? "scale(1.03)" : "scale(1)",
              }}
            >
              {plan.badge && (
                <span
                  className="absolute -top-3 left-6 px-3 py-0.5 rounded-full text-xs font-medium text-white"
                  style={{ backgroundColor: plan.highlight ? "var(--color-primary)" : "var(--color-text-muted)" }}
                >
                  {plan.badge}
                </span>
              )}

              <h3 className="text-lg font-bold mb-1" style={{ color: "var(--color-text-primary)" }}>
                {plan.name}
              </h3>
              <div className="flex items-baseline gap-1 mb-3">
                <span className="text-3xl font-bold" style={{ color: "var(--color-primary)" }}>
                  {formatPrice(plan)}
                </span>
              </div>
              <p className="text-xs mb-5" style={{ color: "var(--color-text-muted)" }}>{plan.desc}</p>

              <div className="mb-5" style={{ height: 1, backgroundColor: "var(--color-border)" }} />

              <ul className="flex-1 space-y-3 mb-6">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                    <span style={{ color: "var(--color-success)", flexShrink: 0 }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>

              {plan.upgradable ? (
                <button
                  onClick={() => void handleUpgrade(plan.tier as "supporter" | "pro")}
                  disabled={upgradingTier !== null}
                  className="w-full py-2.5 text-sm rounded-lg font-medium text-white disabled:opacity-60"
                  style={{ backgroundColor: "var(--color-primary)" }}
                >
                  {upgradingTier === plan.tier ? "处理中…" : plan.actionLabel}
                </button>
              ) : plan.tier === "enterprise" ? (
                <button
                  onClick={() => setContactModalOpen(true)}
                  className="w-full py-2.5 text-sm rounded-lg font-medium text-white"
                  style={{ backgroundColor: "var(--color-primary)" }}
                >
                  联系我们
                </button>
              ) : (
                <button
                  disabled
                  className="w-full py-2.5 text-sm rounded-lg font-medium cursor-not-allowed opacity-50"
                  style={{
                    backgroundColor: "var(--color-bg-surface)",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  {plan.tier === "free" ? "当前默认" : "即将开放"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {message && (
        <p className="text-center text-sm mb-4" style={{ color: "var(--color-success)" }}>{message}</p>
      )}

      {stubMode ? (
        <div
          className="text-center rounded-xl p-6"
          style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
        >
          <p className="text-sm font-medium mb-1" style={{ color: "var(--color-text-primary)" }}>
            {IS_OVERSEAS ? "🚀 Stub mode — upgrades apply instantly" : "🚀 开发模式 — Stub 支付开启"}
          </p>
          <p className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
            {IS_OVERSEAS
              ? "Upgrade buttons work without real payment. Set PAYMENT_STUB_MODE=false to enable Stripe."
              : "升级按钮直接生效，无需真实支付。设置 PAYMENT_STUB_MODE=false 可启用微信支付流程。"}
          </p>
          {!isAuthenticated && (
            <Link to="/register" className="text-sm" style={{ color: "var(--color-primary)" }}>
              {IS_OVERSEAS ? "No account yet? Sign up →" : "还没有账号？立即注册 →"}
            </Link>
          )}
        </div>
      ) : (
        <div
          className="text-center rounded-xl p-6"
          style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
        >
          <p className="text-sm font-medium mb-1" style={{ color: "var(--color-text-primary)" }}>
            {IS_OVERSEAS ? "💳 Stripe Checkout" : "💳 微信支付"}
          </p>
          <p className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
            {IS_OVERSEAS
              ? "Supporter $1.99/mo · Pro $5.99/mo · Billed in USD"
              : "支持者 ¥9.9/月 · 专业版 ¥29.9/月 · 企业版请联系销售定制"}
          </p>
          {!isAuthenticated && (
            <Link to="/register" className="text-sm" style={{ color: "var(--color-primary)" }}>
              {IS_OVERSEAS ? "No account yet? Sign up →" : "还没有账号？立即注册 →"}
            </Link>
          )}
        </div>
      )}

      <SaasModal
        isOpen={contactModalOpen}
        onClose={() => setContactModalOpen(false)}
        title="联系销售 — 企业版定制"
        size="sm"
        footer={
          <>
            <button
              onClick={() => setContactModalOpen(false)}
              className="px-4 py-2 text-sm rounded-lg"
              style={{ color: "var(--color-text-secondary)" }}
            >
              取消
            </button>
            <button
              onClick={() => void handleContactSubmit()}
              disabled={contactSubmitting}
              className="px-4 py-2 text-sm rounded-lg font-medium text-white disabled:opacity-60"
              style={{ backgroundColor: "var(--color-primary)" }}
            >
              {contactSubmitting ? "提交中…" : "提交咨询"}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          {[
            { key: "company_name" as const, label: "公司名称", required: true },
            { key: "contact_name" as const, label: "联系人", required: true },
            { key: "contact_email" as const, label: "邮箱", required: true },
            { key: "contact_phone" as const, label: "电话", required: false },
            { key: "scale" as const, label: "团队规模", required: false },
          ].map(({ key, label, required }) => (
            <div key={key}>
              <label className="block text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                {label}{required && " *"}
              </label>
              <input
                type={key === "contact_email" ? "email" : "text"}
                value={contactForm[key]}
                onChange={(e) => setContactForm((f) => ({ ...f, [key]: e.target.value }))}
                className="w-full px-3 py-2 text-sm rounded-lg border"
                style={{
                  borderColor: "var(--color-border)",
                  backgroundColor: "var(--color-bg-surface)",
                  color: "var(--color-text-primary)",
                }}
              />
            </div>
          ))}
          <div>
            <label className="block text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
              需求描述
            </label>
            <textarea
              value={contactForm.message}
              onChange={(e) => setContactForm((f) => ({ ...f, message: e.target.value }))}
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-lg border resize-none"
              style={{
                borderColor: "var(--color-border)",
                backgroundColor: "var(--color-bg-surface)",
                color: "var(--color-text-primary)",
              }}
              placeholder="请描述您的招聘场景和定制需求…"
            />
          </div>
        </div>
      </SaasModal>

      {/* WeChat Pay 扫码支付弹窗（仅大陆） */}
      {!IS_OVERSEAS && (
      <SaasModal
        isOpen={paymentModalOpen}
        onClose={handleClosePayment}
        title={wechatOrder ? `微信支付 — ¥${wechatOrder.amount}/月` : "微信支付"}
        size="sm"
        footer={
          <div className="flex justify-between items-center w-full">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {pollingOrder ? "等待支付中..." : "扫码完成支付"}
            </span>
            <button
              onClick={handleClosePayment}
              className="px-4 py-2 text-sm rounded-lg"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {pollingOrder ? "取消" : "关闭"}
            </button>
          </div>
        }
      >
        <div className="flex flex-col items-center space-y-4 py-4">
          {wechatOrder?.qr_code_url && wechatOrder.qr_code_url !== "stub://qr_code" ? (
            <>
              <p className="text-sm text-center" style={{ color: "var(--color-text-secondary)" }}>
                请使用微信扫描二维码完成支付
              </p>
              {/* QR Code 渲染（需添加 qrcode 库，此处用占位提示） */}
              <div
                className="w-48 h-48 flex items-center justify-center rounded-lg"
                style={{ backgroundColor: "var(--color-bg-surface)" }}
              >
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(wechatOrder.qr_code_url)}`}
                  alt="微信支付二维码"
                  width={180}
                  height={180}
                  className="rounded"
                />
              </div>
            </>
          ) : (
            <>
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
                style={{ backgroundColor: "var(--color-bg-surface)" }}
              >
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  style={{ color: "var(--color-primary)" }}>
                  <path d="M21 12a9 9 0 1 1-9-9" />
                  <path d="M21 3v6h-6" />
                </svg>
              </div>
              <p className="text-sm text-center font-medium" style={{ color: "var(--color-text-primary)" }}>
                {pollingOrder ? "请在手机上完成支付" : "准备支付"}
              </p>
              <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
                {wechatOrder
                  ? `订单号：${wechatOrder.out_trade_no.slice(-16)}`
                  : "正在创建支付订单..."}
              </p>
              {pollingOrder && (
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  支付成功后页面将自动刷新
                </p>
              )}
            </>
          )}
          {wechatOrder && (
            <div className="w-full pt-2" style={{ borderTop: "1px solid var(--color-border)" }}>
              <div className="flex justify-between text-xs" style={{ color: "var(--color-text-muted)" }}>
                <span>{wechatOrder.tier === "supporter" ? "支持者版" : "专业版"}</span>
                <span>¥{wechatOrder.amount}/月</span>
              </div>
            </div>
          )}
        </div>
      </SaasModal>
      )}
    </div>
  );
}
