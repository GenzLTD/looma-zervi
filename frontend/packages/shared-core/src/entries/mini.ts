/**
 * 小程序专用窄入口 — 仅导出小程序安全模块（由 esbuild 打成 dist/mini/index.js）
 */
export {
  MiniApiClient,
  createMiniApiClient,
  wxStorageAdapter,
  isWechatMiniProgram,
} from "../api/MiniApiClientAdapter";

export type {
  StorageAdapter,
  ApiClientConfig,
  RequestOptions,
  ApiError,
} from "../api/mini-types";

export {
  createAuthApi,
  createChatApi,
  createGameApi,
  createEnterpriseApi,
  createReferralApi,
  createResumeApi,
  createJobsApi,
  createReportsApi,
  createPaymentApi,
  createQuotaApi,
  createNarrativeApi,
  createAct1Api,
  createCreditApi,
  createAnalyticsApi,
  createComplianceApi,
  createTrustApi,
} from "../api/createMiniApi";

export type { MiniApiClientInterface } from "../api/createMiniApi";

// Auth
export type {
  Tier,
  Role,
  User,
  UserProfile,
  AuthResponse,
  LoginResponse,
  RegisterResponse,
  WechatLoginResponse,
  LoginRequest,
  RegisterRequest,
  WechatAuthRequest,
  WechatAuthResponse,
  QuotaRecord,
  QuotaResponse,
  TokenPayload,
} from "../types/auth";

// Chat
export type {
  ChatMessage,
  DocSource,
  AskRequest,
  AskResponse,
  RateRequest,
  LastQueryResponse,
} from "../types/chat";

// Game (backend MBTI enums)
export type {
  Identity,
  PersonalityType,
  TraitKey,
  QuizQuestion,
  QuizOption,
  RankName,
  MissionId,
  Mission,
  GameProfile,
  Fleet,
  FleetMember,
  GameScreen,
  SharePlatform,
  ProfileSyncRequest,
  MissionCompleteRequest,
  MissionCompleteResponse,
  FleetMatchCandidate,
  FleetMatchResponse,
  CreateFleetRequest,
  JoinFleetRequest,
  FleetResponse,
  MyFleetResponse,
} from "../types/game";

// PlanetX quiz / personality
export type {
  Identity as PlanetXIdentity,
  TraitKey as PlanetXTraitKey,
  PersonalityType as PlanetXPersonalityType,
  QuizOption as PlanetXQuizOption,
  QuizQuestion as PlanetXQuizQuestion,
  PlanetXRankName,
  PlanetXMissionId,
  PlanetXGameScreen,
  PlanetXFleet,
} from "../types/planetx-game";

// Resume / jobs
export type {
  ParsedResume,
  ResumeExperience,
  ResumeEducation,
  ResumeProject,
  ResumeUploadResult,
  Job,
  JobMatchItem,
  JobMatchResult,
  JobMatchRequest,
  JobMatchResponse,
  ParsedJob,
  JobUploadResult,
  JobMatchScore,
  CreditAnalysis,
  CheckCompanyRequest,
} from "../types/resume";

// Enterprise
export type {
  CreateEnterpriseRequest,
  JoinEnterpriseRequest,
  EnterpriseProfile,
  Candidate,
  AddCandidateRequest,
  AddCandidateResponse,
} from "../types/enterprise";

// Referral
export type {
  CreateReferralRequest,
  CreateReferralResponse,
  UseReferralRequest,
  UseReferralResponse,
  ReferralCodeEntry,
  ProfileShareView,
  ImportShareRequest,
} from "../types/referral";

// Misc
export type {
  Report,
  ReportType,
  ReportRequest,
  GenerateReportRequest,
  HealthStatus,
  PaginatedResponse,
  Poem,
} from "../types/misc";

// Payment
export type {
  PaymentPlan,
  PlansResponse,
  PaymentStatus,
  UpgradeRequest,
  UpgradeResponse,
  PaymentRegion,
  PaymentTradeType,
  WechatOrderRequest,
  WechatOrderResponse,
  WechatJsapiParams,
} from "../types/payment";

export { PAYMENT_SUPPORTER_PRICES, PAYMENT_PRO_PRICES, DEPRECATED_TIER_ALIASES } from "../types/payment";

// Common
export type { ApiResponse, Pagination } from "../types/common";

// Narrative
export type {
  NarrativeDomain,
  NarrativeEventType,
  NarrativeStartRequest,
  NarrativeStartResponse,
  NarrativeEventRequest,
  NarrativeEndRequest,
  NarrativeFeedbackRequest,
  NarrativeStats,
  Act1DomainSummary,
  Act1Step,
  ConvergenceTexture,
  Act1ContentResponse,
  Act1ChoiceOption,
  Act1SessionState,
  Act1AdvanceResponse,
  Act1ChoiceRequest,
  Act1ChoiceResponse,
  Act1InitRequest,
} from "../types/narrative";

// Brand
export type { BrandId, BrandConfig } from "../types/brand";

// Analytics
export type {
  AnalyticsPlatform,
  ClosedLoopEventName,
  ProductEventPayload,
  MicroFeedbackContext,
  MicroFeedbackRequest,
  FunnelStatsResponse,
} from "../types/analytics";

// Compliance
export type {
  ConsentScope,
  ConsentRecord,
  ConsentStatusResponse,
  ConsentGrantResponse,
  ConsentRequiredResponse,
  ConsentRequiredError,
} from "../types/compliance";

// Trust (PlanetX attestations)
export type {
  TrustClaimType,
  TrustVerificationStatus,
  TrustEvidenceType,
  TrustAttestation,
  TrustAttestationsResponse,
  CreateShareCodeRequest,
  CreateShareCodeResponse,
  TrustShareCode,
  TrustShareCodesResponse,
  TrustVerifyRequest,
  TrustVerifyResponse,
} from "../types/trust";

// Constants
export { QUIZ_QUESTIONS } from "../constants/quiz";
export { PERSONALITY_MAP, PERSONALITY_FALLBACK_MAP } from "../constants/personality";
export { API_ROUTES } from "../constants/routes";
export {
  QUOTA_LIMITS,
  TIER_ORDER,
  TOP_N_LIMIT,
  RESOURCE_ASK,
  RESOURCE_JOB_MATCH,
  RESOURCE_RESUME_PARSE,
  RESOURCE_RAG,
} from "../constants/quota";
export { CLOSED_LOOP_EVENTS, MICRO_FEEDBACK_CONTEXT, ANALYTICS_SESSION_KEY } from "../constants/analytics";
export { CONSENT_SCOPE_LABELS, CONSENT_SCOPE_DESCRIPTIONS } from "../constants/compliance";
export {
  CLAIM_LABEL,
  STATUS_LABEL,
  STATUS_COLOR,
  EVIDENCE_LABEL,
  EVIDENCE_FALLBACK,
  CLAIM_FALLBACK,
  STATUS_FALLBACK_KEY,
} from "../constants/trustLabels";
export { BRAND, BRAND_PLANETX, BRAND_SAAS } from "../types/brand";

// Utils
export { computePersonality, hydratePersonality } from "../utils/quiz";
export { getShareText } from "../utils/share";
export {
  ensureConsent,
  grantConsent,
  hasConsent,
  isConsentRequiredError,
} from "../compliance/ensureConsentMini";

export {
  formatDate,
  formatDateTime,
  formatNumber,
  formatRelativeTime,
  truncate,
  formatPercent,
  clamp,
} from "../utils/format";

export {
  isValidEmail,
  isPasswordStrong,
  isNotEmpty,
  isValidPhone,
  isValidUrl,
} from "../utils/validation";

export { RANK_NAMES, getRankName } from "../types/game";
export { IDENTITY_LABELS, getPlanetXRankName } from "../types/planetx-game";

export const LOOMA_TOKEN_KEY = "looma_token";
