/**
 * @looma/shared-core entry point
 *
 * RULE: This package only contains contracts (types, API factory, constants, utils).
 * It does NOT contain AuthGuard, Store, CSS, or UI components.
 * Changes to exports require dual review (Jason + szbenyx).
 */

// API
export {
  ApiClient,
  createApiClient,
  ApiError,
  webStorageAdapter,
  wxStorageAdapter,
} from "./api/ApiClient";
export type {
  ApiClientConfig,
  StorageAdapter,
  RequestOptions,
} from "./api/ApiClient";

export {
  createAuthApi,
  createChatApi,
  createGameApi,
  createEnterpriseApi,
  createJobPostApi,
  createReferralApi,
  createResumeApi,
  createJobsApi,
  createReportsApi,
  createMatchReportsApi,
  createTrustApi,
  createPaymentApi,
  createQuotaApi,
  createNarrativeApi,
  createAct1Api,
  createCreditApi,
  createAnalyticsApi,
  createComplianceApi,
  createAdminApi,
  createTimelineApi,
  createHuaweiIapApi,
  createHuaweiPushApi,
  createCardApi,
} from "./api/createApi";

// Types
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
  GoogleAuthRequest,
  GoogleAuthResponse,
  QuotaRecord,
  QuotaResponse,
  TokenPayload,
} from "./types/auth";

export type {
  HuaweiAuthRequest,
  HuaweiAuthResponse,
  HuaweiIapNotifyRequest,
  HuaweiIapNotifyResponse,
  HuaweiIapVerifyRequest,
  HuaweiIapVerifyResponse,
  HuaweiPushTokenRequest,
  HuaweiPushRegisterResponse,
  HuaweiPushSendRequest,
  HuaweiPushSendResponse,
  HarmonyCardType,
  HarmonyCardItem,
  HarmonyCardBatchRequest,
} from "./types/harmony";

export type {
  ChatMessage,
  DocSource,
  AskMode,
  AskRequest,
  AskResponse,
  StreamCallbacks,
  RateRequest,
  LastQueryResponse,
} from "./types/chat";

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
  ConsensusStatus,
  MatchSpreadHint,
  MatchConsensusItem,
  MatchConsensusListResponse,
  CreateFleetRequest,
  JoinFleetRequest,
  FleetResponse,
  MyFleetResponse,
} from "./types/game";

export { RANK_NAMES, getRankName } from "./types/game";

// PlanetX game (quiz / personality / identity) — canonical for planetx + miniprogram
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
} from "./types/planetx-game";

export {
  IDENTITY_LABELS,
  getPlanetXRankName,
} from "./types/planetx-game";

export { QUIZ_QUESTIONS } from "./constants/quiz";

export {
  PERSONALITY_MAP,
  PERSONALITY_FALLBACK_MAP,
} from "./constants/personality";

export { computePersonality, hydratePersonality } from "./utils/quiz";

export { getShareText } from "./utils/share";
export {
  deriveMatchUiState,
  consensusStatusLabel,
} from "./utils/matchConsensus";
export type { MatchResultView, MatchUiState } from "./utils/matchConsensus";
export type { SharePlatform as PlanetXSharePlatform } from "./utils/share";

/** JWT localStorage key — G2 aligned (planetx / saas / portal) */
export const LOOMA_TOKEN_KEY = "looma_token";

export type {
  ParsedResume,
  ResumeExperience,
  ResumeEducation,
  ResumeProject,
  ResumeUploadResult,
  ResumeIngestRequest,
  ResumeIngestResponse,
  Job,
  JobMatchItem,
  JobMatchResult,
  JobMatchRequest,
  JobMatchResponse,
  GapItem,
  ParsedJob,
  JobUploadResult,
  JobMatchScore,
  CreditAnalysis,
  CheckCompanyRequest,
  CheckCompanyResponse,
  CreditExtended,
  QccCompanyInfo,
  QccRiskData,
  QccOperationData,
} from "./types/resume";

export type {
  CreateEnterpriseRequest,
  JoinEnterpriseRequest,
  EnterpriseProfile,
  Candidate,
  AddCandidateRequest,
  AddCandidateResponse,
  ContactSalesRequest,
  ContactSalesResponse,
  JobPost,
  JobPostListResponse,
  JobPostMatchesResponse,
  CandidateListResponse,
} from "./types/enterprise";

export type {
  CreateReferralRequest,
  CreateReferralResponse,
  UseReferralRequest,
  UseReferralResponse,
  ReferralCodeEntry,
  ProfileShareView,
  TimelineL1Summary,
  ImportShareRequest,
  ImportShareResponse,
} from "./types/referral";

export type {
  Report,
  ReportType,
  ReportRequest,
  GenerateReportRequest,
  HealthStatus,
  PaginatedResponse,
  ApiError as ApiErrorType,
  Poem,
} from "./types/misc";

export type {
  MatchReport,
  MatchReportSummary,
  MatchReportItem,
  MatchReportMetadata,
  CreateMatchReportRequest,
  MatchReportListResponse,
  ReportSharing,
  ShareDimension,
  ShareMatchReportRequest,
} from "./types/matchReport";

export type {
  TrustClaimType,
  TrustEvidenceType,
  TrustVerificationStatus,
  TrustAttestation,
  TrustAttestationsResponse,
  CreateShareCodeRequest,
  CreateShareCodeResponse,
  TrustShareCode,
  TrustShareCodesResponse,
  TrustVerifyRequest,
  TrustVerifyResponse,
  TrustAuditLogEntry,
  TrustAuditLogResponse,
  TrustPublicKeyResponse,
} from "./types/trust";

export type {
  TimelineEvent,
  TimelineEventKind,
  TimelineListResponse,
  CreateTimelineEventRequest,
  TimelineGrowthResponse,
  TimelineGrowthDimension,
  TimelineBackfillResponse,
  TimelineExportResponse,
  TimelineDeleteAllResponse,
  TimelineSignalQuality,
  TimelineWeightRole,
  TimelineVisibility,
} from "./types/timeline";

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
} from "./types/payment";

export {
  PAYMENT_SUPPORTER_PRICES,
  PAYMENT_PRO_PRICES,
  DEPRECATED_TIER_ALIASES,
} from "./types/payment";

export type {
  ApiResponse,
  Pagination,
  PaginatedResponse as CommonPaginatedResponse,
} from "./types/common";

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
} from "./types/narrative";

export {
  BRAND,
  BRAND_PLANETX,
  BRAND_SAAS,
} from "./types/brand";
export type {
  ChallengePoem,
  ChallengeRound,
  ChallengeEntry,
  ChallengeCurrentResponse,
} from "./types/poetry-challenge";

export type { BrandId, BrandConfig } from "./types/brand";

// Constants
export {
  QUOTA_LIMITS,
  TIER_ORDER,
  TOP_N_LIMIT,
  CANDIDATE_LIMITS,
  JOB_POST_LIMITS,
  RESOURCE_ASK,
  RESOURCE_JOB_MATCH,
  RESOURCE_RESUME_PARSE,
  RESOURCE_RAG,
} from "./constants/quota";

export { API_ROUTES } from "./constants/routes";

export {
  CLAIM_LABEL,
  STATUS_LABEL,
  STATUS_COLOR,
  EVIDENCE_LABEL,
  EVIDENCE_FALLBACK,
  CLAIM_FALLBACK,
  STATUS_FALLBACK_KEY,
} from "./constants/trustLabels";

// Utils
export {
  formatDate,
  formatDateTime,
  formatNumber,
  formatRelativeTime,
  truncate,
  formatPercent,
  clamp,
} from "./utils/format";

export {
  isValidEmail,
  isPasswordStrong,
  isNotEmpty,
  isValidPhone,
  isValidUrl,
} from "./utils/validation";

export {
  hasMinTier,
  isPaidTier,
  isAdmin,
} from "./utils/entitlements";
export type { TierLike } from "./utils/entitlements";

export type {
  AnalyticsPlatform,
  ClosedLoopEventName,
  ProductEventPayload,
  MicroFeedbackContext,
  MicroFeedbackRequest,
  FunnelStatsResponse,
} from "./types/analytics";

export {
  CLOSED_LOOP_EVENTS,
  MICRO_FEEDBACK_CONTEXT,
  ANALYTICS_SESSION_KEY,
} from "./constants/analytics";

export {
  initAnalytics,
  getAnalyticsSessionId,
  trackEvent,
  flushEvents,
} from "./analytics/track";

export type {
  ConsentScope,
  PrimaryConsentScope,
  ConsentRecord,
  ConsentStatusResponse,
  ConsentGrantResponse,
  ConsentRequiredResponse,
  ConsentRequiredError,
} from "./types/compliance";

export {
  CONSENT_SCOPE_LABELS,
  CONSENT_SCOPE_DESCRIPTIONS,
  CONSENT_PRIMARY_TIERS,
  CONSENT_PACKAGES,
  CONSENT_SCOPE_TO_PACKAGE,
  resolveConsentPromptScope,
} from "./constants/compliance";

export {
  ensureConsent,
  grantConsent,
  hasConsent,
  isConsentRequiredError,
} from "./compliance/ensureConsent";

export type {
  AdminStatsResponse,
  AdminRecentUser,
  AdminDauPoint,
  AdminFunnelResponse,
  AdminNarrativeResponse,
  AdminHealthResponse,
} from "./types/admin";
