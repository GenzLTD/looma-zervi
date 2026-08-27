/**
 * API route constants.
 * Centralized so both brands use the same paths and stay aligned with the Flask backend.
 */

export const API_ROUTES = {
  // Auth
  AUTH_REGISTER: "/v1/auth/register",
  AUTH_LOGIN: "/v1/auth/login",
  AUTH_WECHAT: "/v1/auth/wechat",
  AUTH_GOOGLE: "/v1/auth/google",
  AUTH_HUAWEI: "/v1/auth/huawei",
  AUTH_BIND: "/v1/auth/bind",
  AUTH_PROFILE: "/v1/auth/profile",
  AUTH_REFRESH: "/v1/auth/refresh",
  AUTH_BRIDGE: "/v1/auth/bridge",

  // Quota (new top-level path; /v1/auth/quota kept as alias on backend)
  QUOTA: "/v1/quota",

  // Game
  GAME_PROFILE_SYNC: "/v1/game/profile-sync",
  GAME_PROFILE: "/v1/game/profile",
  GAME_MISSION_COMPLETE: "/v1/game/mission-complete",
  GAME_MATCH: "/v1/game/match",
  GAME_MATCH_ACK: "/v1/game/match/acknowledge",
  GAME_MATCH_CONSENSUS: "/v1/game/match/consensus",
  GAME_FLEET_CREATE: "/v1/game/fleet/create",
  GAME_FLEET_JOIN: "/v1/game/fleet/join",
  GAME_FLEET_MINE: "/v1/game/fleet/mine",
  GAME_FLEET_LEAVE: "/v1/game/fleet/leave",
  // Game — HarmonyOS 答题游戏
  GAME_QUIZ_START: "/v1/game/start",
  GAME_QUIZ_ANSWER: "/v1/game/answer",
  GAME_QUIZ_RESULT: "/v1/game/result",
  GAME_QUIZ_HISTORY: "/v1/game/history",

  // Referral / growth
  REFERRAL_CREATE: "/v1/referral/create",
  REFERRAL_USE: "/v1/referral/use",
  REFERRAL_MY_CODES: "/v1/referral/my-codes",
  REFERRAL_PROFILE_VIEW: "/v1/referral/profile-view",

  // Enterprise (T空间 B-end)
  ENTERPRISE_CREATE: "/v1/enterprise/create",
  ENTERPRISE_JOIN: "/v1/enterprise/join",
  ENTERPRISE_PROFILE: "/v1/enterprise/profile",
  ENTERPRISE_CANDIDATES: "/v1/enterprise/candidates",
  ENTERPRISE_CANDIDATE: "/v1/enterprise/candidate",
  ENTERPRISE_CANDIDATES_ADD: "/v1/enterprise/candidates/add",
  ENTERPRISE_CANDIDATES_IMPORT_SHARE: "/v1/enterprise/candidates/import-share",
  ENTERPRISE_CONTACT_SALES: "/v1/enterprise/contact-sales",

  // Job posts (HR 职位发布)
  JOB_POSTS: "/v1/job-posts",
  JOB_POST: "/v1/job-posts",

  // Ask / RAG / Feedback
  ASK: "/v1/ask",
  FEEDBACK_RATE: "/v1/feedback/rate",
  FEEDBACK_LAST_QUERY: "/v1/feedback/last-query",

  // Jobs
  JOBS_LIST: "/v1/jobs/list",
  JOBS_MATCH: "/v1/jobs/match",
  JOBS_UPLOAD: "/v1/jobs/upload",
  JOBS_PARSE: "/v1/jobs/parse",
  // Jobs — HarmonyOS 首页 / 求职门面
  JOBS_ROOT: "/v1/jobs",               // GET — 职位列表（alias of /list）
  JOBS_SEARCH: "/v1/jobs/search",      // GET — 关键字搜索
  JOBS_RECOMMEND: "/v1/jobs/recommend",// GET — AI 推荐
  JOBS_DETAIL: "/v1/jobs",             // GET /:id — 拼接方式: `${JOBS_DETAIL}/${jobId}`
  JOBS_SEED_DEMO: "/v1/jobs/seed-demo", // POST — 持久化演示职位（HR owner）
  JOBS_APPLICATIONS: "/v1/jobs",       // GET `${JOBS_APPLICATIONS}/${jobId}/applications`

  // Applications (seeker apply → HR visible)
  APPLICATION: "/v1/application",      // POST create / GET list mine
  // DELETE/GET one: `${APPLICATION}/${applicationId}`
  // GET report: `${APPLICATION}/${applicationId}/report` — CONTRACT_APPLICATION_REPORT.md

  // Resume
  RESUME_PARSE: "/v1/resume/parse",
  RESUME_UPLOAD: "/v1/resume/upload",
  RESUME_INGEST: "/v1/resume/ingest",
  RESUME_IMPROVE: "/v1/resume/improve",
  // Resume — HarmonyOS 简历管理
  RESUME_LIST: "/v1/resume/list",        // GET — 用户简历列表
  RESUME_ANALYSIS: "/v1/resume/analysis",// GET — AI 分析 (?resume_id=xxx)
  RESUME_DELETE: "/v1/resume",           // DELETE /:id — 拼接方式: `${RESUME_DELETE}/${resumeId}`

  // Reports (ops daily/weekly/monthly)
  REPORTS_GENERATE: "/v1/reports/generate",
  REPORTS_LIST: "/v1/reports/list",

  // Match reports (user-owned resume×JD persistence)
  MATCH_REPORTS: "/v1/match-reports",

  // Payment
  PAYMENT_PLANS: "/v1/payment/plans",
  PAYMENT_STATUS: "/v1/payment/status",
  PAYMENT_UPGRADE: "/v1/payment/upgrade",
  PAYMENT_PROVIDERS: "/v1/payment/providers",
  PAYMENT_CHECKOUT: "/v1/payment/checkout",
  PAYMENT_WECHAT_ORDER: "/v1/payment/wechat/order",
  PAYMENT_WECHAT_NOTIFY: "/v1/payment/wechat/notify",

  // Credit (company evaluation — tripod leg 3: Resume → Job → Company)
  // ⭐ Powered by QCC (企查查) official data source
  CREDIT_ANALYZE: "/v1/credit/analyze",
  CREDIT_CHECK_COMPANY: "/v1/credit/check-company",
  CREDIT_CHECK_COMPANY_DETAIL: "/v1/credit/check-company/detail",

  // Poetry library + Xin-Da-Ya challenge (overseas)
  POETRY_SEARCH: "/v1/poetry/search",
  POETRY_BROWSE: "/v1/poetry/browse",
  POETRY_RANDOM: "/v1/poetry/random",
  POETRY_STATS: "/v1/poetry/stats",
  POETRY_AUTHORS: "/v1/poetry/authors",
  POETRY_CHALLENGE_CURRENT: "/v1/poetry/challenge/current",
  POETRY_CHALLENGE_ENTRIES: "/v1/poetry/challenge/entries",

  // Health
  HEALTH: "/health",

  // Narrative (Phase 0 feedback collection)
  NARRATIVE_START: "/v1/narrative/start",
  NARRATIVE_EVENT: "/v1/narrative/event",
  NARRATIVE_END: "/v1/narrative/end",
  NARRATIVE_FEEDBACK: "/v1/narrative/feedback",
  NARRATIVE_STATS: "/v1/narrative/stats",

  // Act 1 State Machine (GDD §5.1)
  ACT1_INIT: "/v1/narrative/engine/act1/init",
  ACT1_STATE: "/v1/narrative/engine/act1/state",
  ACT1_ADVANCE: "/v1/narrative/engine/act1/advance",
  ACT1_CHOICE: "/v1/narrative/engine/act1/choice",
  ACT1_RESET: "/v1/narrative/engine/act1/reset",
  ACT1_CONTENT: "/v1/narrative/engine/act1/content",

  // Analytics (内测闭环漏斗)
  ANALYTICS_EVENTS: "/v1/analytics/events",
  ANALYTICS_FUNNEL: "/v1/analytics/funnel",
  FEEDBACK_MICRO: "/v1/feedback/micro",

  // Career timeline (behaviour time-series)
  TIMELINE: "/v1/timeline",
  TIMELINE_EVENTS: "/v1/timeline/events",
  TIMELINE_GROWTH: "/v1/timeline/growth",
  TIMELINE_BACKFILL: "/v1/timeline/bridge/backfill",
  TIMELINE_EXPORT: "/v1/timeline/export",
  TIMELINE_DELETE_ME: "/v1/timeline/me",

  // HarmonyOS cloud kits (IAP / Push / Card)
  HUAWEI_IAP_NOTIFY: "/v1/payment/huawei/notify",
  HUAWEI_IAP_VERIFY: "/v1/payment/huawei/verify",
  HUAWEI_PUSH_REGISTER: "/v1/push/huawei/register",
  HUAWEI_PUSH_UNREGISTER: "/v1/push/huawei/unregister",
  HUAWEI_PUSH_SEND: "/v1/push/huawei/send",
  HUAWEI_PUSH_BATCH: "/v1/push/huawei/batch",
  HUAWEI_CARD: "/v1/card",
  HUAWEI_CARD_BATCH: "/v1/card/batch",

  // Trust protocol (attestation cards + share_code verify)
  TRUST_ATTESTATIONS: "/v1/trust/attestations",
  TRUST_REFRESH: "/v1/trust/refresh",
  TRUST_SHARE_CODE: "/v1/trust/share-code",
  TRUST_SHARE_CODES: "/v1/trust/share-codes",
  TRUST_AUDIT_LOG: "/v1/trust/audit-log",
  TRUST_VERIFY: "/v1/trust/verify",
  TRUST_PUBLIC_KEY: "/v1/trust/.well-known/public-key",

  // Compliance (PIPL consent gate)
  COMPLIANCE_CONSENT_GRANT: "/v1/compliance/consent/grant",
  COMPLIANCE_CONSENT_REVOKE: "/v1/compliance/consent/revoke",
  COMPLIANCE_CONSENT_STATUS: "/v1/compliance/consent/status",
  COMPLIANCE_CONSENT_REQUIRED: "/v1/compliance/consent/required",

  // Admin dashboard
  ADMIN_STATS: "/v1/admin/stats",
  ADMIN_FUNNEL: "/v1/admin/funnel",
  ADMIN_NARRATIVE: "/v1/admin/narrative",
  ADMIN_HEALTH: "/v1/admin/health",
} as const;
