/**
 * Quota constants shared across brands.
 * Aligned with backend `src/utils/quota.py`.
 */

export const RESOURCE_ASK = "ask";
export const RESOURCE_JOB_MATCH = "job_match";
export const RESOURCE_RESUME_PARSE = "resume_parse";
export const RESOURCE_RAG = "rag";

export const QUOTA_LIMITS = {
  guest: {
    [RESOURCE_JOB_MATCH]: 1,
    [RESOURCE_ASK]: 3,
    [RESOURCE_RESUME_PARSE]: 1,
    [RESOURCE_RAG]: 2,
  },
  free: {
    [RESOURCE_JOB_MATCH]: 5,
    [RESOURCE_ASK]: 30,
    [RESOURCE_RESUME_PARSE]: 3,
    [RESOURCE_RAG]: 10,
  },
  supporter: {
    [RESOURCE_JOB_MATCH]: 99999,
    [RESOURCE_ASK]: 99999,
    [RESOURCE_RESUME_PARSE]: 99999,
    [RESOURCE_RAG]: 99999,
  },
  pro: {
    [RESOURCE_JOB_MATCH]: 99999,
    [RESOURCE_ASK]: 99999,
    [RESOURCE_RESUME_PARSE]: 99999,
    [RESOURCE_RAG]: 99999,
  },
  enterprise: {
    [RESOURCE_JOB_MATCH]: 99999,
    [RESOURCE_ASK]: 99999,
    [RESOURCE_RESUME_PARSE]: 99999,
    [RESOURCE_RAG]: 99999,
  },
} as const;

export const TIER_ORDER = {
  guest: -1,
  free: 0,
  supporter: 1,
  pro: 2,
  enterprise: 3,
} as const;

export const TOP_N_LIMIT = {
  guest: 3,
  free: 5,
  supporter: 10,
  pro: 10,
  enterprise: 20,
} as const;

/** Aligned with backend `tier_limits.py`. null = unlimited. */
export const CANDIDATE_LIMITS = {
  free: 0,
  supporter: 20,
  pro: 200,
  enterprise: null,
} as const;

export const JOB_POST_LIMITS = {
  free: 0,
  supporter: 3,
  pro: 20,
  enterprise: null,
} as const;
