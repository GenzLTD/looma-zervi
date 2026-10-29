/**
 * API factory functions for MiniProgram.
 * 
 * This is a simplified version of createApi.ts that works with MiniApiClient.
 * Removes Web-specific dependencies (File, ReadableStream, TextDecoder, etc.)
 */

import type {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  WechatAuthRequest,
  WechatAuthResponse,
  UserProfile,
  QuotaResponse,
} from "../types/auth";
import type {
  AskRequest,
  AskResponse,
  StreamCallbacks,
  RateRequest,
  LastQueryResponse,
} from "../types/chat";
import type {
  GameProfile,
  MissionCompleteRequest,
  MissionCompleteResponse,
  FleetMatchResponse,
  FleetMatchRequest,
  MatchConsensusListResponse,
  CreateFleetRequest,
  FleetResponse,
  JoinFleetRequest,
  MyFleetResponse,
  ProfileSyncRequest,
  QuizStartResponse,
  QuizAnswerRequest,
  QuizAnswerResponse,
  QuizResultResponse,
  QuizHistoryResponse,
} from "../types/game";
import type {
  CreateEnterpriseRequest,
  EnterpriseProfile,
  JoinEnterpriseRequest,
  Candidate,
  AddCandidateRequest,
  AddCandidateResponse,
} from "../types/enterprise";
import type { ParsedResume, JobMatchRequest, JobMatchResponse, Job, ParsedJob, CreditAnalysis, CheckCompanyRequest, ResumeListResponse, ResumeAnalysisResponse, ResumeDetail, ResumeUpdateRequest, ResumeIngestRequest, ResumeIngestResponse, ResumePermission, ResumePermissionGrant, ResumeVisibility, ResumeBlacklistItem, ResumeBlacklistAddRequest, ResumeBlacklistResponse, ResumeTemplatesResponse } from "../types/resume";
import type { Report, GenerateReportRequest } from "../types/misc";
import { API_ROUTES } from "../constants/routes";

// 简化的 API 客户端接口，兼容 MiniApiClient
export interface MiniApiClientInterface {
  get<T = any>(url: string, params?: Record<string, any>, options?: any): Promise<T>;
  post<T = any>(url: string, data?: any, options?: any): Promise<T>;
  put<T = any>(url: string, data?: any, options?: any): Promise<T>;
  patch<T = any>(url: string, data?: any, options?: any): Promise<T>;
  delete<T = any>(url: string, options?: any): Promise<T>;
  stream?(url: string, data?: any, callbacks?: any, options?: any): Promise<void>;
  upload?(url: string, file: any, fieldName?: string, options?: any): Promise<any>;
}

// ============================================================
// Auth API
// ============================================================
export function createAuthApi(client: MiniApiClientInterface) {
  return {
    /** Web email/password registration */
    register: (payload: RegisterRequest) =>
      client.post<AuthResponse>(API_ROUTES.AUTH_REGISTER, payload),

    /** Web email/password login */
    login: (payload: LoginRequest) =>
      client.post<AuthResponse>(API_ROUTES.AUTH_LOGIN, payload),

    /** WeChat miniprogram login (wx.login code -> looma JWT) */
    wechat: (payload: WechatAuthRequest) =>
      client.post<WechatAuthResponse>(API_ROUTES.AUTH_WECHAT, payload),

    /** Bind WeChat account to existing email user */
    bind: (code: string) =>
      client.post<{ message: string }>(API_ROUTES.AUTH_BIND, { code }),

    /** Get current user profile */
    profile: () => client.get<UserProfile>(API_ROUTES.AUTH_PROFILE),

    /** Refresh JWT token */
    refresh: () =>
      client.post<{ access_token: string; token_type: "bearer"; expires_in: number }>(
        API_ROUTES.AUTH_REFRESH
      ),

    /** Bridge endpoint (MVP returns 501; no Supabase dependency) */
    bridge: () =>
      client.post<{ error: string; message: string }>(API_ROUTES.AUTH_BRIDGE),

    /** Get current quota usage */
    quota: () => client.get<QuotaResponse>(API_ROUTES.QUOTA),
  };
}

// ============================================================
// Chat / Ask API
// ============================================================
export function createChatApi(client: MiniApiClientInterface) {
  return {
    /** Non-streaming RAG question */
    ask: (payload: AskRequest) => client.post<AskResponse>(API_ROUTES.ASK, payload),

    /** SSE streaming RAG question with callbacks - not supported in miniprogram */
    askStream: async (_payload: AskRequest, _callbacks: StreamCallbacks) => {
      throw new Error('Streaming not supported in miniprogram');
    },

    /** Rate a previous query */
    rate: (payload: RateRequest) =>
      client.post<{ ok: boolean; query_id: number; rating: number }>(API_ROUTES.FEEDBACK_RATE, payload),

    /** Get user's last query ID */
    lastQuery: () => client.get<LastQueryResponse>(API_ROUTES.FEEDBACK_LAST_QUERY),
  };
}

// ============================================================
// Game API
// ============================================================
export function createGameApi(client: MiniApiClientInterface) {
  return {
    /** Sync personality test result to backend */
    profileSync: (payload: ProfileSyncRequest) =>
      client.post<GameProfile>(API_ROUTES.GAME_PROFILE_SYNC, payload),

    /** Get current game profile (XP + level + personality) */
    profile: () => client.get<GameProfile>(API_ROUTES.GAME_PROFILE),

    /** Complete a mission and earn XP */
    missionComplete: (payload: MissionCompleteRequest) =>
      client.post<MissionCompleteResponse>(API_ROUTES.GAME_MISSION_COMPLETE, payload),

    /** Fleet 1:1 personality match (PlanetX domain)
     *  personalize=false 关闭个性化画像匹配（PIPL 自动化决策可拒绝） */
    match: (payload?: FleetMatchRequest) =>
      client.post<FleetMatchResponse>(API_ROUTES.GAME_MATCH, payload ?? {}),

    acknowledgeConsensus: (payload: { consensus_id: string }) =>
      client.post<{ status: string }>(API_ROUTES.GAME_MATCH_ACK, payload),

    listConsensus: () =>
      client.get<MatchConsensusListResponse>(API_ROUTES.GAME_MATCH_CONSENSUS),

    /** Create a new fleet */
    createFleet: (payload: CreateFleetRequest) =>
      client.post<FleetResponse>(API_ROUTES.GAME_FLEET_CREATE, payload),

    /** Join an existing fleet */
    joinFleet: (payload: JoinFleetRequest) =>
      client.post<{ message: string; fleet_id: string; fleet_name: string; captain_id: string; member_count: number }>(
        API_ROUTES.GAME_FLEET_JOIN,
        payload
      ),

    /** Get current user's fleet */
    myFleet: () => client.get<MyFleetResponse>(API_ROUTES.GAME_FLEET_MINE),

    /** Leave current fleet */
    leaveFleet: () => client.post<{ message: string }>(API_ROUTES.GAME_FLEET_LEAVE),

    // ── HarmonyOS 答题游戏 ──
    /** Start a new quiz session */
    quizStart: () => client.post<QuizStartResponse>(API_ROUTES.GAME_QUIZ_START),

    /** Submit an answer for the current question */
    quizAnswer: (payload: QuizAnswerRequest) =>
      client.post<QuizAnswerResponse>(API_ROUTES.GAME_QUIZ_ANSWER, payload),

    /** Get quiz result by session_id */
    quizResult: (sessionId: string) =>
      client.get<QuizResultResponse>(API_ROUTES.GAME_QUIZ_RESULT, { session_id: sessionId }),

    /** Get user's quiz history */
    quizHistory: () => client.get<QuizHistoryResponse>(API_ROUTES.GAME_QUIZ_HISTORY),
  };
}

// ============================================================
// Enterprise API (T空间 B-end)
// ============================================================
export function createEnterpriseApi(client: MiniApiClientInterface) {
  return {
    /** Create a new enterprise */
    create: (payload: CreateEnterpriseRequest) =>
      client.post<{ id: string; name: string; domain: string; role: string }>(
        API_ROUTES.ENTERPRISE_CREATE,
        payload
      ),

    /** Join an existing enterprise */
    join: (payload: JoinEnterpriseRequest) =>
      client.post<{ enterprise_id: string; role: string }>(API_ROUTES.ENTERPRISE_JOIN, payload),

    /** Get current user's enterprise profile */
    profile: () => client.get<EnterpriseProfile>(API_ROUTES.ENTERPRISE_PROFILE),

    /** List candidates for the enterprise */
    candidates: () => client.get<{ candidates: Candidate[] }>(API_ROUTES.ENTERPRISE_CANDIDATES),

    /** Add a candidate to the enterprise */
    addCandidate: (payload: AddCandidateRequest) =>
      client.post<AddCandidateResponse>(API_ROUTES.ENTERPRISE_CANDIDATES_ADD, payload),

    /** Get candidate detail by ID */
    getCandidate: (candidateId: string) =>
      client.get<Candidate>(`${API_ROUTES.ENTERPRISE_CANDIDATE}/${candidateId}`),

    /** Import candidate from PlanetX profile share code */
    importFromShare: (shareCode: string) =>
      client.post<Candidate>(API_ROUTES.ENTERPRISE_CANDIDATES_IMPORT_SHARE, {
        share_code: shareCode,
      }),
  };
}

// ============================================================
// Referral API (growth + profile share)
// ============================================================
export function createReferralApi(client: MiniApiClientInterface) {
  return {
    /** Create invite or profile share code */
    create: (payload?: import("../types/referral").CreateReferralRequest) =>
      client.post<import("../types/referral").CreateReferralResponse>(
        API_ROUTES.REFERRAL_CREATE,
        payload ?? {},
      ),

    /** Consume a referral invite code (not profile_share) */
    use: (code: string) =>
      client.post<import("../types/referral").UseReferralResponse>(API_ROUTES.REFERRAL_USE, {
        code,
      }),

    /** List codes created by current user */
    myCodes: () =>
      client.get<{ codes: import("../types/referral").ReferralCodeEntry[] }>(
        API_ROUTES.REFERRAL_MY_CODES,
      ),

    /** Public: view personality profile by share code (no auth required) */
    profileView: (code: string) =>
      client.get<import("../types/referral").ProfileShareView>(
        `${API_ROUTES.REFERRAL_PROFILE_VIEW}/${encodeURIComponent(code)}`,
      ),
  };
}

// ============================================================
// Resume API (miniprogram不支持文件上传)
// ============================================================
export function createResumeApi(client: MiniApiClientInterface) {
  return {
    /** Parse resume text into structured data */
    parse: (text: string) =>
      client.post<{ extracted: ParsedResume }>(API_ROUTES.RESUME_PARSE, { text }),

    /** Upload resume file for AI parsing - not supported in miniprogram */
    upload: (_file: any) => {
      throw new Error('File upload not supported in miniprogram');
    },

    /** Ingest pre-parsed markdown directly (DemoPeter thin-ingest — no LLM call)；extracted 带上即 processed */
    ingest: (payload: ResumeIngestRequest) =>
      client.post<ResumeIngestResponse>(API_ROUTES.RESUME_INGEST, payload),

    // ── HarmonyOS 简历管理 ──
    /** List all resumes uploaded by current user */
    list: () => client.get<ResumeListResponse>(API_ROUTES.RESUME_LIST),

    /** Get AI analysis for a specific resume */
    analysis: (resumeId: string) =>
      client.get<ResumeAnalysisResponse>(API_ROUTES.RESUME_ANALYSIS, { resume_id: resumeId }),

    /** Delete a resume by ID */
    delete: (resumeId: string) =>
      client.delete<{ message: string; resume_id: string }>(`${API_ROUTES.RESUME_DELETE}/${resumeId}`),

    // ── resume.v1.json v0.1.0 契约端点 ──
    // 阶段3 落地前 8 个端点均为 stub_501；页面用 isNotImplemented(err) 统一降级，
    // 禁止各页面自行判 501/405。
    /** GET /v1/resume/:resume_id — 详情（stub_501 → stage3） */
    detail: (resumeId: string) =>
      client.get<ResumeDetail>(`${API_ROUTES.RESUME_BASE}/${resumeId}`),

    /** PUT /v1/resume/:resume_id — 正文更新（title/extracted/markdown；不含 visibility，写入口归 setPermission） */
    update: (resumeId: string, body: ResumeUpdateRequest) =>
      client.put<ResumeDetail>(`${API_ROUTES.RESUME_BASE}/${resumeId}`, body),

    /** GET /v1/resume/:resume_id/permission — 简历维授权面（仅 owner 可读完整 grants） */
    permission: (resumeId: string) =>
      client.get<ResumePermission>(`${API_ROUTES.RESUME_BASE}/${resumeId}/permission`),

    /** PUT /v1/resume/:resume_id/permission — 全量替换语义；grants 省略即清空，必须先 GET 再 PUT */
    setPermission: (
      resumeId: string,
      body: { visibility: ResumeVisibility; grants?: ResumePermissionGrant[] }
    ) => client.put<ResumePermission>(`${API_ROUTES.RESUME_BASE}/${resumeId}/permission`, body),

    /** GET /v1/resume/blacklist — 用户维屏蔽企业列表 */
    blacklist: () => client.get<ResumeBlacklistResponse>(API_ROUTES.RESUME_BLACKLIST),

    /** POST /v1/resume/blacklist — match 枚举分情况必填 */
    blacklistAdd: (body: ResumeBlacklistAddRequest) =>
      client.post<ResumeBlacklistItem>(API_ROUTES.RESUME_BLACKLIST, body),

    /** DELETE /v1/resume/blacklist/:item_id */
    blacklistRemove: (itemId: string) =>
      client.delete<{ message: string; id: string }>(`${API_ROUTES.RESUME_BLACKLIST}/${itemId}`),

    /** GET /v1/resume/templates — 全局模板目录（0.1 只读；auth optional） */
    templates: () => client.get<ResumeTemplatesResponse>(API_ROUTES.RESUME_TEMPLATES),
  };
}

// ============================================================
// Jobs API (miniprogram不支持文件上传)
// ============================================================
export function createJobsApi(client: MiniApiClientInterface) {
  return {
    /** List available jobs (persisted + mock fallback) */
    list: () => client.get<{ jobs: Job[]; total: number }>(API_ROUTES.JOBS_LIST),

    /** List jobs via root alias (HarmonyOS) */
    listAll: () => client.get<{ jobs: Job[]; total: number }>(API_ROUTES.JOBS_ROOT),

    /** Search jobs by keyword and/or location */
    search: (params: { q?: string; location?: string; page?: number; size?: number }) =>
      client.get<{ jobs: Job[]; total: number }>(API_ROUTES.JOBS_SEARCH, params),

    /** Get job detail by ID */
    detail: (jobId: string) =>
      client.get<{ job: Job }>(`${API_ROUTES.JOBS_DETAIL}/${jobId}`),

    /** Get AI-recommended jobs for current user (requires auth) */
    recommend: () =>
      client.get<{ jobs: (Job & { match_score: number })[]; total: number }>(API_ROUTES.JOBS_RECOMMEND),

    /** Upload JD file for AI parsing - not supported in miniprogram */
    upload: (_file: any) => {
      throw new Error('File upload not supported in miniprogram');
    },

    /** Parse plain JD text into structured data */
    parse: (text: string) =>
      client.post<{ parsed: ParsedJob }>(API_ROUTES.JOBS_PARSE, { text }),

    /** Match resume to job listings (with optional job_id filter) */
    match: (payload: JobMatchRequest & { job_id?: string; job_description?: string }) =>
      client.post<JobMatchResponse>(API_ROUTES.JOBS_MATCH, payload),
  };
}

// ============================================================
// Reports API
// ============================================================
export function createReportsApi(client: MiniApiClientInterface) {
  return {
    /** Generate a daily/weekly/monthly report */
    generate: (payload: GenerateReportRequest) =>
      client.post<Report>(API_ROUTES.REPORTS_GENERATE, payload),

    /** List generated reports */
    list: () => client.get<{ reports: Report[]; total: number }>(API_ROUTES.REPORTS_LIST),
  };
}

// ============================================================
// Credit API (Company evaluation — tripod leg 3)
// ============================================================
export function createCreditApi(client: MiniApiClientInterface) {
  return {
    /** Parse raw credit report text via LLM */
    analyze: (text: string) =>
      client.post<{ extracted: CreditAnalysis }>(API_ROUTES.CREDIT_ANALYZE, { text }),

    /** Evaluate a company by name (post-match flow) */
    checkCompany: (payload: CheckCompanyRequest) =>
      client.post<{ extracted: CreditAnalysis }>(API_ROUTES.CREDIT_CHECK_COMPANY, payload),
  };
}

// ============================================================
// Narrative API (Phase 0 feedback collection)
// ============================================================
export function createNarrativeApi(client: MiniApiClientInterface) {
  return {
    /** Start a new narrative session */
    start: (payload: import("../types/narrative").NarrativeStartRequest) =>
      client.post<import("../types/narrative").NarrativeStartResponse>(
        API_ROUTES.NARRATIVE_START,
        payload,
      ),

    /** Log a narrative event */
    event: (payload: import("../types/narrative").NarrativeEventRequest) =>
      client.post<{ ok: boolean }>(API_ROUTES.NARRATIVE_EVENT, payload),

    /** Mark session complete or abandoned */
    end: (payload: import("../types/narrative").NarrativeEndRequest) =>
      client.post<{ ok: boolean }>(API_ROUTES.NARRATIVE_END, payload),

    /** Submit convergence-point qualitative feedback */
    feedback: (payload: import("../types/narrative").NarrativeFeedbackRequest) =>
      client.post<{ ok: boolean }>(API_ROUTES.NARRATIVE_FEEDBACK, payload),

    /** Admin: get aggregated Phase 0 metrics */
    stats: () =>
      client.get<import("../types/narrative").NarrativeStats>(API_ROUTES.NARRATIVE_STATS),
  };
}

// ============================================================
// Act 1 State Machine API (GDD §5.1)
// ============================================================
export function createAct1Api(client: MiniApiClientInterface) {
  return {
    /** Initialize Act 1 session with a domain */
    init: (payload: import("../types/narrative").Act1InitRequest) =>
      client.post<import("../types/narrative").Act1SessionState>(
        API_ROUTES.ACT1_INIT,
        payload,
      ),

    /** Get current Act 1 state */
    state: (sessionId: string) =>
      client.get<import("../types/narrative").Act1SessionState>(
        `${API_ROUTES.ACT1_STATE}?session_id=${encodeURIComponent(sessionId)}`,
      ),

    /** Advance to next step */
    advance: (sessionId: string) =>
      client.post<import("../types/narrative").Act1AdvanceResponse>(
        API_ROUTES.ACT1_ADVANCE,
        { session_id: sessionId },
      ),

    /** Make a choice at step 3 */
    choice: (payload: import("../types/narrative").Act1ChoiceRequest) =>
      client.post<import("../types/narrative").Act1ChoiceResponse>(
        API_ROUTES.ACT1_CHOICE,
        payload,
      ),

    /** Reset session (hard=true clears domain) */
    reset: (sessionId: string, hard = false) =>
      client.post<{ ok: boolean }>(
        API_ROUTES.ACT1_RESET,
        { session_id: sessionId, hard },
      ),

    /** Get Act 1 content library */
    content: (domain?: string) =>
      client.get<import("../types/narrative").Act1ContentResponse>(
        domain
          ? `${API_ROUTES.ACT1_CONTENT}?domain=${encodeURIComponent(domain)}`
          : API_ROUTES.ACT1_CONTENT,
      ),
  };
}

// ============================================================
// Payment API
// ============================================================
export function createPaymentApi(client: MiniApiClientInterface) {
  return {
    /** List available pricing plans (?region=CN|US) */
    plans: (region?: import("../types/payment").PaymentRegion) => {
      const query = region ? `?region=${region}` : "";
      return client.get<import("../types/payment").PlansResponse>(
        `${API_ROUTES.PAYMENT_PLANS}${query}`,
      );
    },

    /** Get current user subscription status */
    status: () => client.get<import("../types/payment").PaymentStatus>(API_ROUTES.PAYMENT_STATUS),

    /** Upgrade tier (stub: no real payment) */
    upgrade: (tier: "supporter" | "pro") =>
      client.post<import("../types/payment").UpgradeResponse>(API_ROUTES.PAYMENT_UPGRADE, { tier }),

    /** Create WeChat Pay order. region 写在这一单上，微信支付只接受 CN。 */
    wechatOrder: (
      payload: import("../types/payment").WechatOrderRequest,
      region?: import("../types/payment").PaymentRegion,
    ) => {
      const query = region ? `?region=${region}` : "";
      return client.post<import("../types/payment").WechatOrderResponse>(
        `${API_ROUTES.PAYMENT_WECHAT_ORDER}${query}`,
        payload,
      );
    },

    /** Stub only: simulate the WeChat success notify for an existing order. */
    wechatNotifySimulate: (outTradeNo: string) =>
      client.post<{ settled: boolean; out_trade_no: string; tier: string }>(
        API_ROUTES.PAYMENT_WECHAT_NOTIFY_SIMULATE,
        { out_trade_no: outTradeNo },
      ),

    /**
     * List configured payment providers — 同时是 stub_mode 的权威源。
     * /plans 是公开面，契约刻意不带 stub_mode（test_payment_guard），别去那里读。
     */
    providers: (region?: import("../types/payment").PaymentRegion) => {
      const query = region ? `?region=${region}` : "";
      return client.get<import("../types/payment").ProvidersResponse>(
        `${API_ROUTES.PAYMENT_PROVIDERS}${query}`,
      );
    },
  };
}

// ============================================================
// Quota API
// ============================================================
export function createQuotaApi(client: MiniApiClientInterface) {
  return {
    /** Get current quota usage (new path /v1/quota) */
    get: () => client.get<QuotaResponse>(API_ROUTES.QUOTA),
  };
}

// ============================================================
// Analytics API (内测闭环漏斗)
// ============================================================
export function createAnalyticsApi(client: MiniApiClientInterface) {
  return {
    logEvents: (events: import("../types/analytics").ProductEventPayload[]) =>
      client.post<{ ok: boolean; ingested: number }>(API_ROUTES.ANALYTICS_EVENTS, { events }),

    funnel: (days = 30) =>
      client.get<import("../types/analytics").FunnelStatsResponse>(
        API_ROUTES.ANALYTICS_FUNNEL,
        { days },
      ),

    microFeedback: (payload: import("../types/analytics").MicroFeedbackRequest) =>
      client.post<{ ok: boolean; id: number }>(API_ROUTES.FEEDBACK_MICRO, payload),
  };
}

// ============================================================
// Compliance API (PIPL consent gate)
// ============================================================
// ============================================================
// Trust API (PlanetX attestations)
// ============================================================
export function createTrustApi(client: MiniApiClientInterface) {
  return {
    /** List current user attestations */
    listAttestations: () =>
      client.get<import("../types/trust").TrustAttestationsResponse>(API_ROUTES.TRUST_ATTESTATIONS),

    /** Refresh attestation cache */
    refresh: () =>
      client.post<import("../types/trust").TrustAttestationsResponse>(API_ROUTES.TRUST_REFRESH),

    /** Create a profile share code */
    createShareCode: (payload?: import("../types/trust").CreateShareCodeRequest) =>
      client.post<import("../types/trust").CreateShareCodeResponse>(API_ROUTES.TRUST_SHARE_CODE, payload ?? {}),

    /** List user's share codes */
    listShareCodes: () =>
      client.get<import("../types/trust").TrustShareCodesResponse>(API_ROUTES.TRUST_SHARE_CODES),

    /** Revoke a share code */
    revokeShareCode: (codeId: string) =>
      client.delete<{ message: string }>(`${API_ROUTES.TRUST_SHARE_CODE}/${codeId}`),
  };
}

export function createTimelineApi(client: MiniApiClientInterface) {
  return {
    list: (params?: { cursor?: string; limit?: number; kind?: string; since?: string }) => {
      const q: string[] = [];
      if (params?.cursor) q.push(`cursor=${encodeURIComponent(params.cursor)}`);
      if (params?.limit != null) q.push(`limit=${params.limit}`);
      if (params?.kind) q.push(`kind=${encodeURIComponent(params.kind)}`);
      if (params?.since) q.push(`since=${encodeURIComponent(params.since)}`);
      const qs = q.join("&");
      return client.get<import("../types/timeline").TimelineListResponse>(
        qs ? `${API_ROUTES.TIMELINE}?${qs}` : API_ROUTES.TIMELINE,
      );
    },
    createEvent: (payload: import("../types/timeline").CreateTimelineEventRequest) =>
      client.post<import("../types/timeline").TimelineEvent>(API_ROUTES.TIMELINE_EVENTS, payload),
    growth: () =>
      client.get<import("../types/timeline").TimelineGrowthResponse>(API_ROUTES.TIMELINE_GROWTH),
    backfill: () =>
      client.post<import("../types/timeline").TimelineBackfillResponse>(API_ROUTES.TIMELINE_BACKFILL),
  };
}

// ============================================================
// Compliance API (PIPL consent gate)
// ============================================================
export function createComplianceApi(client: MiniApiClientInterface) {
  return {
    grant: (scope: import("../types/compliance").ConsentScope, purpose?: string) =>
      client.post<import("../types/compliance").ConsentGrantResponse>(
        API_ROUTES.COMPLIANCE_CONSENT_GRANT,
        { scope, purpose },
      ),

    grantBatch: (scopes: import("../types/compliance").ConsentScope[]) =>
      client.post<import("../types/compliance").ConsentGrantResponse>(
        API_ROUTES.COMPLIANCE_CONSENT_GRANT,
        { scopes },
      ),

    revoke: (scope: import("../types/compliance").ConsentScope) =>
      client.post<{ revoked: boolean; consent_id?: string; reason?: string }>(
        API_ROUTES.COMPLIANCE_CONSENT_REVOKE,
        { scope },
      ),

    status: () =>
      client.get<import("../types/compliance").ConsentStatusResponse>(
        API_ROUTES.COMPLIANCE_CONSENT_STATUS,
      ),

    required: () =>
      client.get<import("../types/compliance").ConsentRequiredResponse>(
        API_ROUTES.COMPLIANCE_CONSENT_REQUIRED,
      ),
  };
}