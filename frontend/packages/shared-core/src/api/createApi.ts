/**
 * API factory functions.
 *
 * This module aggregates API modules previously scattered across endpoints.ts,
 * with all Supabase references removed and all paths aligned with the new Flask backend.
 */
import { ApiClient } from "./ApiClient";
import type {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  WechatAuthRequest,
  WechatAuthResponse,
  GoogleAuthRequest,
  GoogleAuthResponse,
  UserProfile,
  QuotaResponse,
} from "../types/auth";
import type {
  HarmonyCardBatchRequest,
  HarmonyCardItem,
  HuaweiAuthRequest,
  HuaweiAuthResponse,
  HuaweiIapNotifyRequest,
  HuaweiIapNotifyResponse,
  HuaweiIapVerifyRequest,
  HuaweiIapVerifyResponse,
  HuaweiPushRegisterResponse,
  HuaweiPushSendRequest,
  HuaweiPushSendResponse,
  HuaweiPushTokenRequest,
} from "../types/harmony";
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
  ContactSalesRequest,
  ContactSalesResponse,
  JobPost,
  JobPostListResponse,
  JobPostMatchesResponse,
  CandidateListResponse,
} from "../types/enterprise";
import type { ParsedResume, JobMatchRequest, JobMatchResponse, Job, ResumeUploadResult, ResumeIngestRequest, ResumeIngestResponse, ParsedJob, JobUploadResult, CreditAnalysis, CheckCompanyRequest, CheckCompanyResponse, ResumeListResponse, ResumeAnalysisResponse } from "../types/resume";
import type { Report, GenerateReportRequest } from "../types/misc";
import type {
  CreateMatchReportRequest,
  MatchReport,
  MatchReportListResponse,
  ReportSharing,
  ShareMatchReportRequest,
} from "../types/matchReport";
import type {
  CreateShareCodeRequest,
  CreateShareCodeResponse,
  TrustAttestationsResponse,
  TrustAuditLogResponse,
  TrustPublicKeyResponse,
  TrustShareCodesResponse,
  TrustVerifyRequest,
  TrustVerifyResponse,
} from "../types/trust";
import type {
  CreateTimelineEventRequest,
  TimelineBackfillResponse,
  TimelineDeleteAllResponse,
  TimelineEvent,
  TimelineExportResponse,
  TimelineGrowthResponse,
  TimelineListResponse,
} from "../types/timeline";
import { API_ROUTES } from "../constants/routes";

// ============================================================
// Auth API
// ============================================================
export function createAuthApi(client: ApiClient) {
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

    /** Google OAuth login (overseas ID token -> looma JWT) */
    google: (payload: GoogleAuthRequest) =>
      client.post<GoogleAuthResponse>(API_ROUTES.AUTH_GOOGLE, payload),

    /** Huawei Account Kit login (authorizationCode -> looma JWT) */
    huawei: (payload: HuaweiAuthRequest) =>
      client.post<HuaweiAuthResponse>(API_ROUTES.AUTH_HUAWEI, payload),

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
export function createChatApi(client: ApiClient) {
  return {
    /** Non-streaming RAG question */
    ask: (payload: AskRequest) => client.post<AskResponse>(API_ROUTES.ASK, payload),

    /** SSE streaming RAG question with callbacks */
    askStream: async (payload: AskRequest, callbacks: StreamCallbacks) => {
      const stream = await client.stream(API_ROUTES.ASK, payload);
      const reader = stream.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const data = trimmed.slice(5).trim();
            if (data === "[DONE]") continue;
            try {
              const parsed = JSON.parse(data);
              callbacks.onMessage?.(parsed);
            } catch {
              callbacks.onMessage?.(data);
            }
          }
        }

        // Flush any remaining bytes
        if (buffer.trim()) {
          const trimmed = buffer.trim();
          if (trimmed.startsWith("data:")) {
            const data = trimmed.slice(5).trim();
            if (data !== "[DONE]") {
              try {
                callbacks.onMessage?.(JSON.parse(data));
              } catch {
                callbacks.onMessage?.(data);
              }
            }
          }
        }

        callbacks.onComplete?.();
      } catch (err) {
        callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
      } finally {
        reader.releaseLock();
      }
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
export function createGameApi(client: ApiClient) {
  return {
    /** Sync personality test result to backend */
    profileSync: (payload: ProfileSyncRequest) =>
      client.post<GameProfile>(API_ROUTES.GAME_PROFILE_SYNC, payload),

    /** Get current game profile (XP + level + personality) */
    profile: () => client.get<GameProfile>(API_ROUTES.GAME_PROFILE),

    /** Complete a mission and earn XP */
    missionComplete: (payload: MissionCompleteRequest) =>
      client.post<MissionCompleteResponse>(API_ROUTES.GAME_MISSION_COMPLETE, payload),

    /** Fleet 1:1 personality match (PlanetX domain) */
    match: () => client.post<FleetMatchResponse>(API_ROUTES.GAME_MATCH),

    /** 双向共识确认（阶段二） */
    acknowledgeConsensus: (payload: { consensus_id: string }) =>
      client.post<{ status: string; consensus_status?: string }>(
        API_ROUTES.GAME_MATCH_ACK,
        payload,
      ),

    /** 待办 / 已验证共识列表（阶段二） */
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
export function createEnterpriseApi(client: ApiClient) {
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
    candidates: () => client.get<CandidateListResponse>(API_ROUTES.ENTERPRISE_CANDIDATES),

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

    /** Submit enterprise sales inquiry */
    contactSales: (payload: ContactSalesRequest) =>
      client.post<ContactSalesResponse>(API_ROUTES.ENTERPRISE_CONTACT_SALES, payload),
  };
}

// ============================================================
// Job Post API (HR 职位发布)
// ============================================================
export function createJobPostApi(client: ApiClient) {
  return {
    list: () => client.get<JobPostListResponse>(API_ROUTES.JOB_POSTS),

    create: (payload: Pick<JobPost, "title" | "company" | "description" | "requirements" | "status">) =>
      client.post<JobPost>(API_ROUTES.JOB_POSTS, payload),

    update: (postId: string, payload: Partial<Pick<JobPost, "title" | "company" | "description" | "requirements" | "status">>) =>
      client.put<JobPost>(`${API_ROUTES.JOB_POST}/${postId}`, payload),

    remove: (postId: string) =>
      client.delete<{ ok: boolean }>(`${API_ROUTES.JOB_POST}/${postId}`),

    matches: (postId: string) =>
      client.get<JobPostMatchesResponse>(`${API_ROUTES.JOB_POST}/${postId}/matches`),
  };
}

// ============================================================
// Referral API (growth + profile share)
// ============================================================
export function createReferralApi(client: ApiClient) {
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
// Resume API
// ============================================================
export function createResumeApi(client: ApiClient) {
  return {
    /** Parse resume text into structured data */
    parse: (text: string) =>
      client.post<{ extracted: ParsedResume }>(API_ROUTES.RESUME_PARSE, { text }),

    /** Upload resume file for AI parsing (PDF/DOCX → structured JSON) */
    upload: (file: File) => client.upload<ResumeUploadResult>(API_ROUTES.RESUME_UPLOAD, file, "file"),

    /** Ingest pre-parsed markdown directly (DemoPeter thin-ingest — no LLM call) */
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
  };
}

// ============================================================
// Jobs API
// ============================================================
export function createJobsApi(client: ApiClient) {
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

    /** Upload JD file for AI parsing (PDF/DOCX → structured JSON) */
    upload: (file: File) => client.upload<JobUploadResult>(API_ROUTES.JOBS_UPLOAD, file, "file"),

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
export function createReportsApi(client: ApiClient) {
  return {
    /** Generate a daily/weekly/monthly report */
    generate: (payload: GenerateReportRequest) =>
      client.post<Report>(API_ROUTES.REPORTS_GENERATE, payload),

    /** List generated reports */
    list: () => client.get<{ reports: Report[]; total: number }>(API_ROUTES.REPORTS_LIST),
  };
}

export function createMatchReportsApi(client: ApiClient) {
  return {
    create: (payload: CreateMatchReportRequest) =>
      client.post<MatchReport>(API_ROUTES.MATCH_REPORTS, payload),

    list: (params?: { page?: number; page_size?: number }) => {
      const q = new URLSearchParams();
      if (params?.page) q.set("page", String(params.page));
      if (params?.page_size) q.set("page_size", String(params.page_size));
      const qs = q.toString();
      return client.get<MatchReportListResponse>(
        qs ? `${API_ROUTES.MATCH_REPORTS}?${qs}` : API_ROUTES.MATCH_REPORTS,
      );
    },

    get: (id: string) =>
      client.get<MatchReport>(`${API_ROUTES.MATCH_REPORTS}/${id}`),

    export: (id: string) =>
      client.get<MatchReport>(`${API_ROUTES.MATCH_REPORTS}/${id}/export`),

    remove: (id: string) =>
      client.delete<{ ok: boolean; id: string }>(`${API_ROUTES.MATCH_REPORTS}/${id}`),

    listSharings: (id: string) =>
      client.get<{ sharings: ReportSharing[] }>(
        `${API_ROUTES.MATCH_REPORTS}/${id}/sharings`,
      ),

    share: (id: string, payload: ShareMatchReportRequest) =>
      client.post<ReportSharing>(`${API_ROUTES.MATCH_REPORTS}/${id}/share`, payload),

    updateShare: (id: string, sharingId: string, payload: ShareMatchReportRequest) =>
      client.put<ReportSharing>(
        `${API_ROUTES.MATCH_REPORTS}/${id}/share/${sharingId}`,
        payload,
      ),

    revokeShare: (id: string, sharingId: string) =>
      client.delete<ReportSharing>(
        `${API_ROUTES.MATCH_REPORTS}/${id}/share/${sharingId}`,
      ),
  };
}

// ============================================================
// Trust API (attestation cards + share_code verify)
// ============================================================
export function createTrustApi(client: ApiClient) {
  return {
    listAttestations: () =>
      client.get<TrustAttestationsResponse>(API_ROUTES.TRUST_ATTESTATIONS),

    refresh: () =>
      client.post<TrustAttestationsResponse>(API_ROUTES.TRUST_REFRESH),

    createShareCode: (payload?: CreateShareCodeRequest) =>
      client.post<CreateShareCodeResponse>(API_ROUTES.TRUST_SHARE_CODE, payload ?? {}),

    listShareCodes: () =>
      client.get<TrustShareCodesResponse>(API_ROUTES.TRUST_SHARE_CODES),

    revokeShareCode: (codeId: string) =>
      client.delete<{ message: string }>(`${API_ROUTES.TRUST_SHARE_CODE}/${codeId}`),

    auditLog: (limit?: number) => {
      const q = limit != null ? `?limit=${limit}` : "";
      return client.get<TrustAuditLogResponse>(`${API_ROUTES.TRUST_AUDIT_LOG}${q}`);
    },

    /** Public — no JWT; authorised via share_code */
    verify: (payload: TrustVerifyRequest) =>
      client.post<TrustVerifyResponse>(API_ROUTES.TRUST_VERIFY, payload),

    /** Public — Ed25519 PEM for offline signature checks */
    publicKey: () =>
      client.get<TrustPublicKeyResponse>(API_ROUTES.TRUST_PUBLIC_KEY),
  };
}

// ============================================================
// Credit API (Company evaluation — tripod leg 3)
// ============================================================
export function createCreditApi(client: ApiClient) {
  return {
    /** Parse raw credit report text via LLM */
    analyze: (text: string) =>
      client.post<{ extracted: CreditAnalysis }>(API_ROUTES.CREDIT_ANALYZE, { text }),

    /** Evaluate a company by name (post-match flow) — powered by QCC official data */
    checkCompany: (payload: CheckCompanyRequest) =>
      client.post<CheckCompanyResponse>(API_ROUTES.CREDIT_CHECK_COMPANY, payload),

    /** Full detailed credit check with all QCC categories */
    checkCompanyDetail: (payload: { company_name: string }) =>
      client.post<CheckCompanyResponse>(API_ROUTES.CREDIT_CHECK_COMPANY_DETAIL, payload),
  };
}

// ============================================================
// Narrative API (Phase 0 feedback collection)
// ============================================================
export function createNarrativeApi(client: ApiClient) {
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
export function createAct1Api(client: ApiClient) {
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
export function createPaymentApi(client: ApiClient) {
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

    /** Upgrade tier (stub mode only; blocked in production → use checkout instead) */
    upgrade: (tier: "supporter" | "pro") =>
      client.post<import("../types/payment").UpgradeResponse>(API_ROUTES.PAYMENT_UPGRADE, { tier }),

    /** Create WeChat Pay order (production mode) */
    wechatOrder: (payload: import("../types/payment").WechatOrderRequest) =>
      client.post<import("../types/payment").WechatOrderResponse>(
        API_ROUTES.PAYMENT_WECHAT_ORDER,
        payload,
      ),

    /** List configured overseas payment providers */
    providers: (region?: import("../types/payment").PaymentRegion) => {
      const query = region ? `?region=${region}` : "";
      return client.get<import("../types/payment").ProvidersResponse>(
        `${API_ROUTES.PAYMENT_PROVIDERS}${query}`,
      );
    },

    /** Create unified checkout session (Stripe / PayPal / Airwallex) */
    checkout: (payload: import("../types/payment").CheckoutRequest) =>
      client.post<import("../types/payment").CheckoutResponse>(
        API_ROUTES.PAYMENT_CHECKOUT,
        payload,
      ),
  };
}

// ============================================================
// Quota API
// ============================================================
export function createQuotaApi(client: ApiClient) {
  return {
    /** Get current quota usage (new path /v1/quota) */
    get: () => client.get<QuotaResponse>(API_ROUTES.QUOTA),
  };
}

// ============================================================
// Analytics API (内测闭环漏斗)
// ============================================================
export function createAnalyticsApi(client: ApiClient) {
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
// Admin API (Management dashboard)
// ============================================================
export function createAdminApi(client: ApiClient) {
  return {
    /** Full admin dashboard stats (users, activity, system) */
    stats: () =>
      client.get<import("../types/admin").AdminStatsResponse>(API_ROUTES.ADMIN_STATS),

    /** Funnel conversion stats */
    funnel: (days = 30) =>
      client.get<import("../types/admin").AdminFunnelResponse>(
        API_ROUTES.ADMIN_FUNNEL,
        { days },
      ),

    /** Narrative / Phase 0 metrics */
    narrative: () =>
      client.get<import("../types/admin").AdminNarrativeResponse>(API_ROUTES.ADMIN_NARRATIVE),

    /** Enhanced system health */
    health: () =>
      client.get<import("../types/admin").AdminHealthResponse>(API_ROUTES.ADMIN_HEALTH),
  };
}

// ============================================================
// Compliance API (PIPL consent gate)
// ============================================================
export function createComplianceApi(client: ApiClient) {
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

// ============================================================
// Timeline API (career behaviour time-series)
// ============================================================
export function createTimelineApi(client: ApiClient) {
  return {
    list: (params?: { cursor?: string; limit?: number; kind?: string; since?: string }) => {
      const q = new URLSearchParams();
      if (params?.cursor) q.set("cursor", params.cursor);
      if (params?.limit != null) q.set("limit", String(params.limit));
      if (params?.kind) q.set("kind", params.kind);
      if (params?.since) q.set("since", params.since);
      const qs = q.toString();
      return client.get<TimelineListResponse>(
        qs ? `${API_ROUTES.TIMELINE}?${qs}` : API_ROUTES.TIMELINE,
      );
    },

    createEvent: (payload: CreateTimelineEventRequest) =>
      client.post<TimelineEvent>(API_ROUTES.TIMELINE_EVENTS, payload),

    deleteEvent: (eventId: string) =>
      client.delete<{ ok: boolean; id: string }>(`${API_ROUTES.TIMELINE_EVENTS}/${eventId}`),

    growth: () => client.get<TimelineGrowthResponse>(API_ROUTES.TIMELINE_GROWTH),

    backfill: () =>
      client.post<TimelineBackfillResponse>(API_ROUTES.TIMELINE_BACKFILL),

    exportMyData: () =>
      client.get<TimelineExportResponse>(API_ROUTES.TIMELINE_EXPORT),

    deleteAllMyData: () =>
      client.delete<TimelineDeleteAllResponse>(
        `${API_ROUTES.TIMELINE_DELETE_ME}?confirm=yes`,
      ),
  };
}

// ============================================================
// HarmonyOS cloud kits (IAP / Push / Card)
// ============================================================
export function createHuaweiIapApi(client: ApiClient) {
  return {
    /** Client-side purchase → server RSA verify + deliver */
    notify: (payload: HuaweiIapNotifyRequest) =>
      client.post<HuaweiIapNotifyResponse>(API_ROUTES.HUAWEI_IAP_NOTIFY, payload),

    /** Server-side order verify (MVP stub → 501) */
    verify: (payload: HuaweiIapVerifyRequest) =>
      client.post<HuaweiIapVerifyResponse>(API_ROUTES.HUAWEI_IAP_VERIFY, payload),
  };
}

export function createHuaweiPushApi(client: ApiClient) {
  return {
    register: (payload: HuaweiPushTokenRequest) =>
      client.post<HuaweiPushRegisterResponse>(
        API_ROUTES.HUAWEI_PUSH_REGISTER,
        payload,
      ),

    unregister: (payload: HuaweiPushTokenRequest) =>
      client.post<HuaweiPushRegisterResponse>(
        API_ROUTES.HUAWEI_PUSH_UNREGISTER,
        payload,
      ),

    send: (payload: HuaweiPushSendRequest) =>
      client.post<HuaweiPushSendResponse>(API_ROUTES.HUAWEI_PUSH_SEND, payload),

    batch: (payload: Record<string, unknown>) =>
      client.post<HuaweiPushSendResponse>(API_ROUTES.HUAWEI_PUSH_BATCH, payload),
  };
}

export function createCardApi(client: ApiClient) {
  return {
    get: (cardId: string, type?: string) => {
      const q = type ? `?type=${encodeURIComponent(type)}` : "";
      return client.get<HarmonyCardItem>(`${API_ROUTES.HUAWEI_CARD}/${cardId}${q}`);
    },

    batch: (payload: HarmonyCardBatchRequest) =>
      client.post<{ cards: HarmonyCardItem[] }>(
        API_ROUTES.HUAWEI_CARD_BATCH,
        payload,
      ),
  };
}

