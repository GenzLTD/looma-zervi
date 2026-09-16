"""
SQLite Database Manager with WAL mode.
Handles all database operations for looma backend.

Tables:
  - users              (core, joint ownership)
  - game_profiles      (Jason owns)
  - fleets             (Jason owns)
  - fleet_members      (Jason owns)
  - mission_completions(Jason owns)
  - enterprises        (szbenyx owns)
  - enterprise_users   (szbenyx owns)
  - candidates         (szbenyx owns)
  - invite_codes       (joint)
  - usage_logs         (joint)
  - trust_memories     (joint — append-only trust behaviour log)
  - trust_attestations (joint — verifiable claim cards)
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)


def _dt_now():
    """Helper for consistent datetime strings."""
    return datetime.now()


def email_hash(email: str | None) -> str | None:
    """Canonical email hash shared with DemoPPI / GFCC (Bridge 2/3).

    Both sides compute sha256 of the lowercased, trimmed email as lowercase hex
    so PlanetX (Python) and DemoPPI (TypeScript) yield identical digests for the
    same mailbox. Returns None for empty email (miniprogram-only users).
    """
    if not email:
        return None
    normalized = email.lower().strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


SCHEMA_SQL = """
-- ============================================
-- Core: users (joint ownership - dual review)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,          -- looma uuid4
    email           TEXT UNIQUE,               -- Web registration (nullable for miniprogram-only)
    email_hash      TEXT,                      -- sha256(lower(trim(email))) for chain B user_id_hash
    password_hash   TEXT,                      -- bcrypt hash (nullable for miniprogram-only)
    wechat_openid   TEXT UNIQUE,               -- WeChat miniprogram login
    supabase_uid    TEXT UNIQUE,               -- Supabase Auth user UUID (THOMAS 统一身份, RFC supabase-unified-auth-v1)
    name            TEXT DEFAULT '',
    tier            TEXT DEFAULT 'free',       -- free | supporter | pro
    role            TEXT DEFAULT 'user',       -- user | admin
    is_early_adopter INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
-- NOTE: idx_users_email_hash 由 init_schema 迁移块创建（旧库需先 ALTER 加列）
CREATE INDEX IF NOT EXISTS idx_users_wechat_openid ON users(wechat_openid);
-- NOTE: idx_users_supabase_uid 由 init_schema 迁移块创建（旧库需先 ALTER 加列）

-- ============================================
-- Core: user_identities (multi-platform identity linking)
-- Supports Google, Apple, WeChat, email+password → one user
-- ============================================
CREATE TABLE IF NOT EXISTS user_identities (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    provider        TEXT NOT NULL,              -- google | apple | wechat | email
    provider_uid    TEXT NOT NULL,              -- platform-specific user ID (sub / openid / email)
    provider_email  TEXT,                       -- email from provider (if available)
    provider_name   TEXT,                       -- display name from provider
    metadata_json   TEXT DEFAULT '{}',          -- extra provider data (avatar, locale, etc.)
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(provider, provider_uid)
);

CREATE INDEX IF NOT EXISTS idx_user_identities_user ON user_identities(user_id);
CREATE INDEX IF NOT EXISTS idx_user_identities_provider ON user_identities(provider, provider_uid);

-- ============================================
-- Game: game_profiles (Jason owns)
-- ============================================
CREATE TABLE IF NOT EXISTS game_profiles (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL,
    identity            TEXT,                  -- PlanetX: explorer | captain | wanderer
    personality_type    TEXT,                  -- MBTI or custom type
    personality_detail  TEXT,                  -- JSON blob with full analysis
    xp                  INTEGER DEFAULT 0,
    level               INTEGER DEFAULT 1,
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_game_profiles_user ON game_profiles(user_id);

-- ============================================
-- Game: fleets (Jason owns)
-- ============================================
CREATE TABLE IF NOT EXISTS fleets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    captain_id      TEXT NOT NULL,
    description     TEXT DEFAULT '',
    invite_code     TEXT UNIQUE,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (captain_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS fleet_members (
    id          TEXT PRIMARY KEY,
    fleet_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    joined_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (fleet_id) REFERENCES fleets(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(fleet_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_fleet_members_user ON fleet_members(user_id);

-- ============================================
-- Game: mission_completions (Jason owns)
-- ============================================
CREATE TABLE IF NOT EXISTS mission_completions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    mission_id  TEXT NOT NULL,
    xp_reward   INTEGER DEFAULT 0,
    completed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, mission_id)
);

CREATE INDEX IF NOT EXISTS idx_missions_user ON mission_completions(user_id);

-- ============================================
-- Trust Layer: trust_memories (joint — append-only behaviour log)
-- ============================================
CREATE TABLE IF NOT EXISTS trust_memories (
    id              TEXT PRIMARY KEY,          -- UUID
    user_id         TEXT NOT NULL,
    session_type    TEXT NOT NULL,             -- quiz | fleet | match | ask | share
    session_id      TEXT NOT NULL,
    memory_content  TEXT NOT NULL,             -- JSON: structured behaviour snapshot
    memory_level    INTEGER DEFAULT 1,         -- 1=surface, 2=deep, 3=fragment, 4=taboo
    created_at      TEXT DEFAULT (datetime('now')),  -- immutable
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_trust_memories_user ON trust_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_trust_memories_session ON trust_memories(session_type, session_id);

-- ============================================
-- Trust Layer: trust_attestations (joint — verifiable claim cards)
-- ============================================
CREATE TABLE IF NOT EXISTS trust_attestations (
    id                  TEXT PRIMARY KEY,          -- UUID
    candidate_id        TEXT NOT NULL,
    claim_type          TEXT NOT NULL,             -- identity | collaboration | communication | influence
    claim_statement     TEXT NOT NULL,
    evidence_type       TEXT NOT NULL,             -- quiz | fleet_consensus | dialogue_analysis | share_signal
    evidence_refs       TEXT DEFAULT '[]',         -- JSON array: trust_memories.id list
    verification_status TEXT DEFAULT 'unverified', -- verified | weak | unverified | contradicted
    confidence_score    REAL DEFAULT 0.0,          -- 0-1 internal only, never shown to users
    generated_by        TEXT DEFAULT 'trust_agent_v0',
    signature           TEXT DEFAULT '',                -- Ed25519 looma_sig_v1:...
    expires_at          TEXT DEFAULT NULL,              -- ISO 8601, 90 days from issued_at
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (candidate_id) REFERENCES users(id),
    UNIQUE(candidate_id, claim_type)               -- one attestation per candidate per claim type
);

CREATE INDEX IF NOT EXISTS idx_trust_attestations_candidate ON trust_attestations(candidate_id);
CREATE INDEX IF NOT EXISTS idx_trust_attestations_type ON trust_attestations(claim_type, verification_status);

-- ============================================
-- Signal bridge ingest (Bridge 2/3 inbound idempotency)
-- ============================================
CREATE TABLE IF NOT EXISTS signal_ingest (
    signal_type      TEXT NOT NULL,
    user_email_hash  TEXT NOT NULL,
    nonce            TEXT NOT NULL,
    payload_json     TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (signal_type, user_email_hash, nonce)
);

-- ============================================
-- Signal bridge outbox (R2: 出站事务性发件箱 — PlanetX 发送侧)
-- 同一 nonce 只能存在一行;body 为已序列化信封原文(重放时逐字节复用,
-- 保证 X-Signature 不变 → 对端 nonce 幂等 → 不重复处理)。
-- ============================================
CREATE TABLE IF NOT EXISTS signal_outbox (
    id              TEXT PRIMARY KEY,
    nonce           TEXT NOT NULL UNIQUE,
    signal_type     TEXT NOT NULL,                      -- personality_beacon | consensus_match | ...
    body            TEXT NOT NULL,                      -- json.dumps(envelope, separators=(",", ":")) 原文
    status          TEXT NOT NULL DEFAULT 'pending',    -- pending | delivered
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    delivered_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_signal_outbox_status ON signal_outbox(status, created_at);

-- ============================================
-- Signal bridge DLQ (R2: 可重放死信队列 — 值班按 nonce 重发)
-- ============================================
CREATE TABLE IF NOT EXISTS signal_dlq (
    id              TEXT PRIMARY KEY,
    nonce           TEXT NOT NULL UNIQUE,
    signal_type     TEXT NOT NULL,
    body            TEXT NOT NULL,
    reason          TEXT NOT NULL,                      -- permanent_4xx | network_error
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    moved_at        TEXT DEFAULT (datetime('now')),
    replayed_at     TEXT                                -- 值班重发成功时间
);

CREATE INDEX IF NOT EXISTS idx_signal_dlq_moved ON signal_dlq(moved_at);

-- ============================================
-- Enterprise: enterprises (szbenyx owns)
-- ============================================
CREATE TABLE IF NOT EXISTS enterprises (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    domain          TEXT,                      -- e.g. "genz.ltd"
    plan            TEXT DEFAULT 'free',       -- free | pro | enterprise
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS enterprise_users (
    id              TEXT PRIMARY KEY,
    enterprise_id   TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    role            TEXT DEFAULT 'member',     -- member | admin
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(enterprise_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_users_enterprise ON enterprise_users(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_enterprise_users_user ON enterprise_users(user_id);

-- ============================================
-- Enterprise: candidates (szbenyx owns)
-- ============================================
CREATE TABLE IF NOT EXISTS candidates (
    id              TEXT PRIMARY KEY,
    enterprise_id   TEXT NOT NULL,
    user_id         TEXT,                      -- linked looma user (nullable)
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    status          TEXT DEFAULT 'new',        -- new | contacted | interviewed | hired | rejected
    profile_data    TEXT,                      -- JSON blob (personality, skills, etc.)
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_candidates_enterprise ON candidates(enterprise_id);

-- ============================================
-- Enterprise: job_posts (szbenyx — HR 职位发布)
-- ============================================
CREATE TABLE IF NOT EXISTS job_posts (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL,
    company         TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    requirements    TEXT DEFAULT '',
    status          TEXT DEFAULT 'active',     -- active | closed | draft
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_job_posts_user ON job_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_job_posts_status ON job_posts(user_id, status);

-- ============================================
-- Job applications (DemoPeter thin-ingest → HR 可见投递)
-- ============================================
CREATE TABLE IF NOT EXISTS applications (
    id                TEXT PRIMARY KEY,
    seeker_user_id    TEXT NOT NULL,
    resume_id         TEXT NOT NULL,           -- documents.id (resume)
    job_id            TEXT NOT NULL,           -- documents.metadata.job_id or job_posts.id
    enterprise_id     TEXT DEFAULT '',
    status            TEXT DEFAULT 'submitted', -- submitted | withdrawn
    metadata          TEXT DEFAULT '{}',       -- JSON, no vector payloads
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    withdrawn_at      TEXT DEFAULT NULL,
    FOREIGN KEY (seeker_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_applications_seeker ON applications(seeker_user_id);
CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
-- One active application per (seeker, resume, job)
CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_active_unique
    ON applications(seeker_user_id, resume_id, job_id) WHERE status = 'submitted';

-- ============================================
-- Enterprise: sales_inquiries (szbenyx — 企业版联系销售)
-- ============================================
CREATE TABLE IF NOT EXISTS sales_inquiries (
    id              TEXT PRIMARY KEY,
    user_id         TEXT,
    company_name    TEXT NOT NULL,
    contact_name    TEXT NOT NULL,
    contact_email   TEXT NOT NULL,
    contact_phone   TEXT DEFAULT '',
    scale           TEXT DEFAULT '',
    message         TEXT DEFAULT '',
    status          TEXT DEFAULT 'new',        -- new | contacted | closed
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_sales_inquiries_status ON sales_inquiries(status);

-- ============================================
-- Payment: orders (szbenyx — 支付订单)
-- ============================================
CREATE TABLE IF NOT EXISTS orders (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    plan_id         TEXT NOT NULL,
    tier            TEXT NOT NULL,
    amount          REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'CNY',
    out_trade_no    TEXT UNIQUE NOT NULL,
    transaction_id  TEXT,
    status          TEXT DEFAULT 'pending',     -- pending | paid | expired | refunded
    prepay_id       TEXT,
    qr_code_url     TEXT,
    metadata_json   TEXT DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now')),
    paid_at         TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_trade_no ON orders(out_trade_no);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- ============================================
-- Payment: subscriptions (szbenyx — 用户订阅状态)
-- ============================================
CREATE TABLE IF NOT EXISTS subscriptions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL UNIQUE,
    tier            TEXT NOT NULL,
    plan_id         TEXT NOT NULL,
    status          TEXT DEFAULT 'active',      -- active | expired | cancelled
    started_at      TEXT DEFAULT (datetime('now')),
    expires_at      TEXT NOT NULL,
    auto_renew      INTEGER DEFAULT 0,
    cancel_at_period_end INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires ON subscriptions(expires_at);

-- ============================================
-- Push: huawei_push_tokens (HarmonyOS Push Kit)
-- ============================================
CREATE TABLE IF NOT EXISTS huawei_push_tokens (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    push_token      TEXT NOT NULL,
    created_at      INTEGER DEFAULT (strftime('%s','now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_push_token ON huawei_push_tokens(push_token);
CREATE INDEX IF NOT EXISTS idx_push_user ON huawei_push_tokens(user_id);

-- ============================================
-- Growth: invite_codes (joint ownership)
-- ============================================
CREATE TABLE IF NOT EXISTS invite_codes (
    id              TEXT PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,
    created_by      TEXT,                      -- user_id of creator
    used_by         TEXT,                      -- user_id of user who used it
    tier_grant      TEXT DEFAULT 'free',       -- tier granted when code is used
    expires_at      TEXT,
    used_at         TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (used_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_invite_codes_code ON invite_codes(code);

-- ============================================
-- Usage: usage_logs (joint)
-- ============================================
CREATE TABLE IF NOT EXISTS usage_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    tokens_used     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_user_date ON usage_logs(user_id, created_at);

-- ============================================
-- LLM usage: llm_usage (joint) — 每次 LLM 调用埋点，供运维面审计
-- ============================================
CREATE TABLE IF NOT EXISTS llm_usage (
    id           TEXT PRIMARY KEY,
    user_id      TEXT,                          -- NULL = 系统/后台调用
    provider     TEXT NOT NULL,
    model        TEXT NOT NULL,
    tokens_in    INTEGER DEFAULT 0,
    tokens_out   INTEGER DEFAULT 0,
    cost_yuan    REAL DEFAULT 0,                -- 按 llm_catalog 折算
    latency_ms   INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'ok',             -- ok / error
    error        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_provider_date ON llm_usage(provider, created_at);
CREATE INDEX IF NOT EXISTS idx_llm_usage_user_date ON llm_usage(user_id, created_at);

-- ============================================
-- Quota: quota_records (joint)
-- ============================================
CREATE TABLE IF NOT EXISTS quota_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    resource TEXT NOT NULL,
    date TEXT NOT NULL,
    used INTEGER DEFAULT 0,
    daily_limit INTEGER NOT NULL,
    UNIQUE(user_id, resource, date)
);

CREATE INDEX IF NOT EXISTS idx_quota_records_user ON quota_records(user_id, resource, date);

-- ============================================
-- Quota: boost_packs (joint)
-- ============================================
CREATE TABLE IF NOT EXISTS boost_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    pack_name TEXT NOT NULL DEFAULT '标准加量包',
    credits INTEGER NOT NULL,
    credits_used INTEGER DEFAULT 0,
    price_yuan INTEGER DEFAULT 29,
    purchased_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    status TEXT DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_boost_packs_user ON boost_packs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_boost_packs_expires ON boost_packs(expires_at);

-- ============================================
-- Quota: boost_consumptions (joint)
-- ============================================
CREATE TABLE IF NOT EXISTS boost_consumptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    boost_pack_id INTEGER NOT NULL REFERENCES boost_packs(id),
    resource TEXT NOT NULL,
    credits_consumed INTEGER DEFAULT 1,
    consumed_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_boost_consumptions_user ON boost_consumptions(user_id);

-- ============================================
-- Poetry: poems (Jason)
-- ============================================
CREATE TABLE IF NOT EXISTS poems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    dynasty TEXT NOT NULL DEFAULT '',
    theme TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    tags TEXT DEFAULT '',              -- comma-separated tags for filtering
    source TEXT DEFAULT 'imported',    -- imported | manual
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(title, author)
);

CREATE INDEX IF NOT EXISTS idx_poems_dynasty ON poems(dynasty);
CREATE INDEX IF NOT EXISTS idx_poems_author ON poems(author);
CREATE INDEX IF NOT EXISTS idx_poems_theme ON poems(theme);
CREATE INDEX IF NOT EXISTS idx_poems_title ON poems(title);

-- ============================================
-- Poetry challenge: 信达雅英译赛 (Jason / overseas)
-- ============================================
CREATE TABLE IF NOT EXISTS challenge_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_key TEXT NOT NULL UNIQUE,          -- e.g. 2026-W29
    poem_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',    -- open | closed
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (poem_id) REFERENCES poems(id)
);

CREATE INDEX IF NOT EXISTS idx_challenge_rounds_status ON challenge_rounds(status);
CREATE INDEX IF NOT EXISTS idx_challenge_rounds_ends ON challenge_rounds(ends_at);

CREATE TABLE IF NOT EXISTS challenge_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    translation TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    license_accepted INTEGER NOT NULL DEFAULT 0,
    vote_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(round_id, user_id),
    FOREIGN KEY (round_id) REFERENCES challenge_rounds(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_challenge_entries_round ON challenge_entries(round_id);

-- ============================================
-- Knowledge: documents (szbenyx)
-- ============================================
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    doc_type TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    chunk_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- ============================================
-- Knowledge: chunks (szbenyx)
-- ============================================
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    char_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);

-- ============================================
-- Knowledge: query_logs (joint — data flywheel)
-- ============================================
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    provider TEXT NOT NULL,
    response_time_ms REAL DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    rating INTEGER DEFAULT NULL,
    intent_label TEXT DEFAULT NULL,
    user_id TEXT DEFAULT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_logs_time ON query_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_query_logs_user ON query_logs(user_id);

-- ============================================
-- Narrative: sessions (Jason — Phase 0 feedback)
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT DEFAULT NULL,          -- nullable (guests can play)
    domain          TEXT NOT NULL,              -- which domain was chosen
    status          TEXT DEFAULT 'active',       -- active | completed | abandoned
    duration_seconds REAL DEFAULT 0,
    started_at      TEXT DEFAULT (datetime('now')),
    ended_at        TEXT DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_narrative_sessions_user ON narrative_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_narrative_sessions_domain ON narrative_sessions(domain);

-- ============================================
-- Narrative: events (Jason — Phase 0 event log)
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL,              -- domain_enter | choice_made | convergence_reached | share_attempt | replay
    domain          TEXT DEFAULT NULL,
    choice          TEXT DEFAULT NULL,
    navigator_line  TEXT DEFAULT NULL,
    metadata_json   TEXT DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES narrative_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_narrative_events_session ON narrative_events(session_id);
CREATE INDEX IF NOT EXISTS idx_narrative_events_type ON narrative_events(event_type);

-- ============================================
-- Narrative: feedback (Jason — Phase 0 convergence feedback)
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    resonated       INTEGER NOT NULL DEFAULT 0, -- 0/1: did Navigator touch you?
    navigator_quote TEXT DEFAULT NULL,           -- recalled Navigator line
    would_replay    INTEGER DEFAULT NULL,        -- 0/1/2 (no/maybe/yes)
    shared          INTEGER NOT NULL DEFAULT 0, -- 0/1
    share_channel   TEXT DEFAULT NULL,           -- wechat | moments | link | other
    open_feedback   TEXT DEFAULT NULL,           -- free-text qualitative
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES narrative_sessions(id),
    UNIQUE(session_id)
);

CREATE INDEX IF NOT EXISTS idx_narrative_feedback_session ON narrative_feedback(session_id);

-- ============================================
-- Domain Engine: value imprints (Jason — GDD §3.2)
-- ============================================
CREATE TABLE IF NOT EXISTS value_imprints (
    user_id         TEXT NOT NULL,
    survival        INTEGER NOT NULL DEFAULT 0,
    freedom         INTEGER NOT NULL DEFAULT 0,
    belonging       INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- Navigator Memory: memory entries (Jason — GDD §3.4)
-- ============================================
CREATE TABLE IF NOT EXISTS navigator_memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    memory_level    TEXT NOT NULL,              -- surface | deep | fragment | taboo
    content         TEXT NOT NULL,
    context         TEXT DEFAULT NULL,
    domain          TEXT DEFAULT NULL,
    choice          TEXT DEFAULT NULL,
    importance      REAL DEFAULT 1.0,
    referenced_count INTEGER DEFAULT 0,
    session_id      TEXT DEFAULT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_navigator_memories_user ON navigator_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_navigator_memories_level ON navigator_memories(memory_level);

-- ============================================
-- Domain Engine: emergent strategy log (Jason — GDD §7.3)
-- ============================================
CREATE TABLE IF NOT EXISTS emergent_strategy_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    strategy_type   TEXT NOT NULL,              -- poetry_refuge | trust_farming | unknown_speedrun | mbti_rejector | cross_domain_hacker
    triggered_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_emergent_strategy_user ON emergent_strategy_log(user_id);

-- ============================================
-- Domain Engine: domain visit log (Jason)
-- ============================================
CREATE TABLE IF NOT EXISTS domain_visits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    domain          TEXT NOT NULL,
    previous_domain TEXT DEFAULT NULL,
    interaction_level TEXT DEFAULT NULL,        -- intended | acceptable | forbidden
    echo_triggered  INTEGER NOT NULL DEFAULT 0, -- 0/1
    entered_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (session_id) REFERENCES narrative_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_domain_visits_user ON domain_visits(user_id);
CREATE INDEX IF NOT EXISTS idx_domain_visits_session ON domain_visits(session_id);

-- ============================================
-- Product analytics: closed-loop funnel (内测)
-- ============================================
CREATE TABLE IF NOT EXISTS product_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name      TEXT NOT NULL,
    user_id         TEXT DEFAULT NULL,
    session_id      TEXT DEFAULT NULL,
    platform        TEXT DEFAULT 'unknown',
    share_code      TEXT DEFAULT NULL,
    source          TEXT DEFAULT 'client',
    success         INTEGER NOT NULL DEFAULT 1,
    properties_json TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_product_events_name ON product_events(event_name);
CREATE INDEX IF NOT EXISTS idx_product_events_created ON product_events(created_at);
CREATE INDEX IF NOT EXISTS idx_product_events_share ON product_events(share_code);

CREATE TABLE IF NOT EXISTS micro_feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    context         TEXT NOT NULL,
    score           INTEGER NOT NULL,
    optional_text   TEXT DEFAULT NULL,
    user_id         TEXT DEFAULT NULL,
    session_id      TEXT DEFAULT NULL,
    platform        TEXT DEFAULT 'unknown',
    share_code      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_micro_feedback_context ON micro_feedback(context);

-- ============================================
-- Narrative: Act 1 state persistence
-- ============================================
CREATE TABLE IF NOT EXISTS act1_sessions (
    session_id      TEXT PRIMARY KEY,
    state_json      TEXT NOT NULL,
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES narrative_sessions(id)
);

-- ============================================
-- Compliance: consents (joint — PIPL consent)
-- ============================================
CREATE TABLE IF NOT EXISTS consents (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    scope           TEXT NOT NULL,              -- e.g. 'resume_upload', 'credit_query'
    purpose         TEXT DEFAULT '',            -- human-readable purpose
    status          TEXT DEFAULT 'granted',     -- granted | revoked | expired
    ip              TEXT DEFAULT '',
    user_agent      TEXT DEFAULT '',
    granted_at      TEXT DEFAULT (datetime('now')),
    revoked_at      TEXT DEFAULT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Only one active grant per (user_id, scope); multiple revoked records allowed for history
CREATE UNIQUE INDEX IF NOT EXISTS idx_consents_active ON consents(user_id, scope) WHERE status='granted';
CREATE INDEX IF NOT EXISTS idx_consents_user ON consents(user_id);
CREATE INDEX IF NOT EXISTS idx_consents_scope ON consents(scope);

-- ============================================
-- Compliance: audit_logs (joint — immutable audit trail)
-- ============================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id              TEXT PRIMARY KEY,
    actor           TEXT NOT NULL,              -- user_id performing the action
    action          TEXT NOT NULL,              -- e.g. 'resume_parse', 'credit_check'
    resource_type   TEXT NOT NULL,              -- e.g. 'resume', 'job', 'consent'
    resource_id     TEXT DEFAULT '',
    consent_id      TEXT DEFAULT '',            -- associated consent record
    metadata        TEXT DEFAULT '{}',          -- JSON, NO PII
    ip              TEXT DEFAULT '',
    user_agent      TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_time ON audit_logs(created_at);

-- ============================================
-- Analytics: product_events (joint — PII-whitelisted)
-- ============================================
CREATE TABLE IF NOT EXISTS product_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name      TEXT NOT NULL,
    user_id         TEXT DEFAULT '',
    properties      TEXT DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_product_events_name ON product_events(event_name);
CREATE INDEX IF NOT EXISTS idx_product_events_time ON product_events(created_at);

-- ============================================
-- Game: quiz_sessions (HarmonyOS 答题游戏)
-- ============================================
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    questions_json  TEXT NOT NULL DEFAULT '[]',   -- JSON array of all QuizQuestion
    current_index   INTEGER NOT NULL DEFAULT 0,
    answers_json    TEXT NOT NULL DEFAULT '[]',   -- JSON array of {question_id, option_ids, score}
    total_score     INTEGER NOT NULL DEFAULT 0,
    total_questions INTEGER NOT NULL DEFAULT 0,
    correct_count   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active', -- active | completed
    result_type     TEXT DEFAULT '',
    insights_json   TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_quiz_sessions_user ON quiz_sessions(user_id, created_at);

-- ============================================
-- Match reports (resume × JD matching persistence)
-- ============================================
CREATE TABLE IF NOT EXISTS match_reports (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    resume_id       TEXT DEFAULT '',
    resume_snapshot TEXT DEFAULT '',
    title           TEXT DEFAULT '',
    status          TEXT DEFAULT 'completed',   -- draft | completed | archived | deleted
    summary         TEXT DEFAULT '',
    metadata        TEXT DEFAULT '{}',          -- JSON: { total_jobs, matched_at, pipeline_version }
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_match_reports_user ON match_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_match_reports_created ON match_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_match_reports_status ON match_reports(status);

CREATE TABLE IF NOT EXISTS match_report_items (
    id                      TEXT PRIMARY KEY,
    report_id               TEXT NOT NULL,
    job_title               TEXT NOT NULL,
    company_name            TEXT NOT NULL,
    location                TEXT DEFAULT '',
    salary_range            TEXT DEFAULT '',
    jd_snapshot             TEXT DEFAULT '',
    overall_score           REAL DEFAULT 0,
    background_match        REAL DEFAULT 0,
    skills_overlap          REAL DEFAULT 0,
    experience_relevance    REAL DEFAULT 0,
    seniority               REAL DEFAULT 0,
    language_requirement    REAL DEFAULT 0,
    company_score           REAL DEFAULT 0,
    salary_match            REAL DEFAULT 0,
    location_match          REAL DEFAULT 0,
    culture_workload_match  REAL DEFAULT 0,
    match_reason            TEXT DEFAULT '',
    matched_skills          TEXT DEFAULT '[]',
    missing_skills          TEXT DEFAULT '[]',
    fit_bullets             TEXT DEFAULT '[]',
    gap_analysis            TEXT DEFAULT '[]',
    improvement_plan        TEXT DEFAULT '',
    credit_snapshot         TEXT DEFAULT '{}',
    rank_order              INTEGER DEFAULT 0,
    created_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (report_id) REFERENCES match_reports(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_report_items_report ON match_report_items(report_id);
CREATE INDEX IF NOT EXISTS idx_report_items_company ON match_report_items(company_name);

-- ============================================
-- Report sharing (career_partner slice; multi-industry later)
-- ============================================
CREATE TABLE IF NOT EXISTS report_sharing (
    id                  TEXT PRIMARY KEY,
    report_id           TEXT NOT NULL,
    user_id             TEXT NOT NULL,
    shared_with_type    TEXT NOT NULL DEFAULT 'career_partner',
    shared_with_id      TEXT DEFAULT '',
    shared_dimensions   TEXT NOT NULL DEFAULT '[]',
    purpose             TEXT DEFAULT '',
    status              TEXT DEFAULT 'active',   -- active | revoked | expired
    granted_at          TEXT DEFAULT (datetime('now')),
    revoked_at          TEXT DEFAULT NULL,
    expires_at          TEXT DEFAULT NULL,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (report_id) REFERENCES match_reports(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_sharing_report ON report_sharing(report_id);
CREATE INDEX IF NOT EXISTS idx_sharing_user ON report_sharing(user_id);
CREATE INDEX IF NOT EXISTS idx_sharing_status ON report_sharing(status);
CREATE INDEX IF NOT EXISTS idx_sharing_type ON report_sharing(shared_with_type);

-- ============================================
-- Trust Layer: share_codes (joint — temporary access grants)
-- ============================================
CREATE TABLE IF NOT EXISTS share_codes (
    id              TEXT PRIMARY KEY,              -- UUID
    code            TEXT UNIQUE NOT NULL,           -- sc_{random}
    owner_id        TEXT NOT NULL,                  -- candidate user_id who generated it
    scope           TEXT NOT NULL DEFAULT '[]',     -- JSON array: authorised claim_types
    max_access_count INTEGER NOT NULL DEFAULT 10,
    access_count    INTEGER NOT NULL DEFAULT 0,
    expires_at      TEXT NOT NULL,                  -- ISO 8601
    status          TEXT NOT NULL DEFAULT 'active', -- active | revoked | expired
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_share_codes_code ON share_codes(code);
CREATE INDEX IF NOT EXISTS idx_share_codes_owner ON share_codes(owner_id);

-- ============================================
-- Trust Layer: verification_audit_log (joint — immutable access trail)
-- ============================================
CREATE TABLE IF NOT EXISTS verification_audit_log (
    id              TEXT PRIMARY KEY,              -- UUID
    share_code      TEXT NOT NULL,                 -- which code was used
    owner_id        TEXT NOT NULL,                 -- candidate whose data was accessed
    verifier_info   TEXT DEFAULT '',               -- caller IP / user-agent / optional identity
    attestation_ids TEXT NOT NULL DEFAULT '[]',    -- JSON array of accessed attestation IDs
    result          TEXT NOT NULL DEFAULT 'success', -- success | expired | exhausted | not_found
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_verification_audit_owner ON verification_audit_log(owner_id, created_at);
CREATE INDEX IF NOT EXISTS idx_verification_audit_code ON verification_audit_log(share_code);

-- ============================================
-- Timeline: career time-series (product surface)
-- See docs/TIMELINE_EVENT_MODEL.md · contracts/timeline.v1.json
-- Not product_events (funnel) · Not narrative_events (game) · Not trust_memories (evidence raw)
-- ============================================
CREATE TABLE IF NOT EXISTS timeline_events (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL,
    event_kind        TEXT NOT NULL,
    occurred_at       TEXT NOT NULL,
    recorded_at       TEXT NOT NULL DEFAULT (datetime('now')),
    source_system     TEXT NOT NULL,
    source_ref        TEXT DEFAULT '',
    title             TEXT DEFAULT '',
    summary           TEXT DEFAULT '',
    payload_json      TEXT DEFAULT '{}',
    signal_quality    TEXT NOT NULL DEFAULT 'observed',
    confidence        REAL DEFAULT 0.5,
    weight_role       TEXT NOT NULL DEFAULT 'evidence',
    visibility        TEXT NOT NULL DEFAULT 'private',
    consent_scope     TEXT DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'active',
    superseded_by     TEXT DEFAULT NULL,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_timeline_user_time
    ON timeline_events(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_user_kind
    ON timeline_events(user_id, event_kind, occurred_at);
CREATE INDEX IF NOT EXISTS idx_timeline_source
    ON timeline_events(source_system, source_ref);

-- ============================================
-- Match consensus (PlanetX phase-2 gate)
-- See 首次星际匹配_子项目接口契约.md · ENGINEERING_CLOSED_LOOP_P0
-- ============================================
CREATE TABLE IF NOT EXISTS match_consensus (
    id              TEXT PRIMARY KEY,
    fleet_id        TEXT NOT NULL,
    initiator_id    TEXT NOT NULL,
    candidate_id    TEXT NOT NULL,
    match_score     INTEGER NOT NULL,
    status          TEXT DEFAULT 'pending',
    reason          TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    verified_at     TEXT,
    expires_at      TEXT NOT NULL,
    FOREIGN KEY (initiator_id) REFERENCES users(id),
    FOREIGN KEY (candidate_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_match_consensus_initiator
    ON match_consensus(initiator_id, status);
CREATE INDEX IF NOT EXISTS idx_match_consensus_candidate
    ON match_consensus(candidate_id, status);

"""


# ============================================
# Beta seed data
# ============================================
BETA_USERS = [
    {"name": "测试用户-免费版",   "email": "beta_free@looma.test",       "tier": "free",       "is_early_adopter": 1},
    {"name": "测试用户-支持者",   "email": "beta_supporter@looma.test",  "tier": "supporter",  "is_early_adopter": 1},
    {"name": "测试用户-专业版",   "email": "beta_pro@looma.test",        "tier": "pro",        "is_early_adopter": 1},
    {"name": "测试用户-管理员",   "email": "beta_admin@looma.test",      "tier": "pro",        "is_early_adopter": 1, "role": "admin"},
]

# 测试账号邮箱后缀白名单：只有这些后缀的账号允许被批量清理。
# 真人邮箱域名（qq.com / 163.com / gmail.com / sjtu.edu.cn 等）均不在此列，
# 因此清理动作在结构上不可能误删真人账号。
TEST_EMAIL_SUFFIXES = (
    "@test.local",
    "@test.com",
    "@example.com",
    "@looma-test.internal",
    "@genz-test.ltd",
)

# 无外键引用 users、但列中持有用户标识的表：(表名, 列名, 是否审计轨迹)
# 这些表不会被沿外键的删除遍历覆盖，必须显式补扫，否则删除账号后会留下孤儿行
# 污染分析口径（query_logs / product_events 直接参与用量统计）。
NON_FK_USER_TABLES = (
    ("query_logs", "user_id", False),
    ("product_events", "user_id", False),
    ("audit_logs", "actor", True),   # 审计轨迹默认保留，include_audit=True 时才清
)


class DatabaseManager:
    """Thread-safe SQLite manager with WAL mode.

    For in-memory databases (testing), uses URI format with cache=shared
    so that all connections share the same in-memory DB.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._is_memory = db_path == ":memory:"
        if not self._is_memory:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    def _connect(self):
        """Create a new SQLite connection."""
        if self._is_memory:
            # Use URI format to share in-memory DB across connections
            conn = sqlite3.connect(
                "file:memdb1?mode=memory&cache=shared",
                uri=True,
            )
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        if not self._is_memory:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")  # 5s busy-wait 缓解 SQLITE_BUSY
        return conn

    @contextmanager
    def get_conn(self):
        """Get a SQLite connection with WAL mode enabled."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self):
        """Initialize all tables. Safe to call on every startup."""
        with self.get_conn() as conn:
            # Pre-migration: SCHEMA_SQL 里的 idx_users_email_hash 引用 email_hash 列，
            # 而 CREATE TABLE IF NOT EXISTS 不改已有旧表结构 —— 旧库必须先 ALTER 补列，
            # 否则 executescript 会在建索引时报 no such column（云端 /health 500 根因）
            try:
                conn.execute("ALTER TABLE users ADD COLUMN email_hash TEXT")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    logger.warning(
                        "Pre-migration ALTER TABLE users ADD COLUMN email_hash failed: %s", e
                    )
            conn.executescript(SCHEMA_SQL)
            # Migration: add invite_code to existing fleets tables
            try:
                conn.execute("ALTER TABLE fleets ADD COLUMN invite_code TEXT")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    logger.warning(
                        "Migration ALTER TABLE fleets ADD COLUMN invite_code failed: %s", e
                    )
            try:
                conn.execute("DROP INDEX IF EXISTS idx_fleets_invite_code")
                conn.execute(
                    "CREATE UNIQUE INDEX idx_fleets_invite_code ON fleets(invite_code)"
                )
            except sqlite3.OperationalError as e:
                logger.warning(
                    "Migration UNIQUE INDEX idx_fleets_invite_code failed: %s", e
                )
            try:
                conn.execute("ALTER TABLE game_profiles ADD COLUMN identity TEXT")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    logger.warning(
                        "Migration ALTER TABLE game_profiles ADD COLUMN identity failed: %s", e
                    )
            # Migration: trust protocol columns on existing trust_attestations
            try:
                conn.execute(
                    "ALTER TABLE trust_attestations ADD COLUMN signature TEXT DEFAULT ''"
                )
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    logger.warning(
                        "Migration ALTER TABLE trust_attestations ADD COLUMN signature failed: %s", e
                    )
            try:
                conn.execute(
                    "ALTER TABLE trust_attestations ADD COLUMN expires_at TEXT DEFAULT NULL"
                )
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    logger.warning(
                        "Migration ALTER TABLE trust_attestations ADD COLUMN expires_at failed: %s", e
                    )
            # Migration: trust_attestations UNIQUE(candidate_id, claim_type) for upsert ON CONFLICT
            try:
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_trust_attestations_claim "
                    "ON trust_attestations(candidate_id, claim_type)"
                )
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                logger.warning(
                    "Migration UNIQUE INDEX trust_attestations_claim failed: %s", e
                )
            # Migration: email_hash for GFCC chain B / DemoPPI match
            try:
                conn.execute("ALTER TABLE users ADD COLUMN email_hash TEXT")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    logger.warning(
                        "Migration ALTER TABLE users ADD COLUMN email_hash failed: %s", e
                    )
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_users_email_hash ON users(email_hash)"
                )
            except sqlite3.OperationalError as e:
                logger.warning(
                    "Migration INDEX idx_users_email_hash failed: %s", e
                )
            for uid, em in conn.execute(
                "SELECT id, email FROM users WHERE email IS NOT NULL AND email_hash IS NULL"
            ).fetchall():
                conn.execute(
                    "UPDATE users SET email_hash = ?, updated_at = datetime('now') WHERE id = ?",
                    (email_hash(em), uid),
                )
            # Migration: supabase_uid for THOMAS unified auth (RFC supabase-unified-auth-v1)
            try:
                conn.execute("ALTER TABLE users ADD COLUMN supabase_uid TEXT")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    logger.warning(
                        "Migration ALTER TABLE users ADD COLUMN supabase_uid failed: %s", e
                    )
            try:
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_supabase_uid ON users(supabase_uid)"
                )
            except sqlite3.OperationalError as e:
                logger.warning(
                    "Migration UNIQUE INDEX idx_users_supabase_uid failed: %s", e
                )

    # ============================================
    # User operations (joint)
    # ============================================
    def create_user(self, email=None, password_hash=None, wechat_openid=None, name=""):
        """Create a new user. email and wechat_openid are both nullable."""
        user_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO users (id, email, email_hash, password_hash, wechat_openid, name)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, email, email_hash(email), password_hash, wechat_openid, name)
            )
        return user_id

    def get_user_by_email(self, email: str):
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def get_user_by_email_hash(self, email_hash_value: str):
        """Resolve a user by canonical email hash (chain B / DemoPPI match)."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email_hash = ?", (email_hash_value,)
            ).fetchone()
        return dict(row) if row else None

    def record_signal_ingest(
        self, signal_type: str, user_email_hash: str, nonce: str, payload_json: str
    ) -> bool:
        """Record an inbound signal for idempotency. Returns True if new, False if duplicate.

        PRIMARY KEY (signal_type, user_email_hash, nonce) guarantees at-most-once
        processing per signal instance (Bridge 2/3 envelope).
        """
        with self.get_conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO signal_ingest (signal_type, user_email_hash, nonce, payload_json)
                       VALUES (?, ?, ?, ?)""",
                    (signal_type, user_email_hash, nonce, payload_json),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    # ============================================
    # Signal bridge outbox + DLQ (R2: 事务性发件箱 + 可重放死信)
    # ============================================
    def enqueue_signal_outbox(self, signal_type: str, nonce: str, body: str) -> bool:
        """入箱(pending)。nonce 唯一,重复入箱返回 False(幂等)。"""
        with self.get_conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO signal_outbox (id, nonce, signal_type, body)
                       VALUES (?, ?, ?, ?)""",
                    (str(uuid.uuid4()), nonce, signal_type, body),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def get_outbox_by_nonce(self, nonce: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM signal_outbox WHERE nonce = ?", (nonce,)
            ).fetchone()
        return dict(row) if row else None

    def list_outbox_pending(self, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM signal_outbox
                   WHERE status = 'pending' ORDER BY created_at LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_outbox_delivered(self, nonce: str) -> None:
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE signal_outbox
                   SET status = 'delivered', delivered_at = datetime('now')
                   WHERE nonce = ?""",
                (nonce,),
            )

    def bump_outbox_attempt(self, nonce: str, error: str) -> None:
        """网络失败:attempts+1 并记录 last_error,仍留 pending 等下次投递。"""
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE signal_outbox
                   SET attempts = attempts + 1, last_error = ?
                   WHERE nonce = ?""",
                (error[:500], nonce),
            )

    def move_outbox_to_dlq(self, nonce: str, reason: str, error: str = "") -> bool:
        """把一条 pending 从 outbox 迁入 DLQ(原 body 逐字节保留)。
        outbox 状态置 'dlq'(终态之一,不再被 list_outbox_pending 扫描)。返回是否迁成。"""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM signal_outbox WHERE nonce = ?", (nonce,)
            ).fetchone()
            if not row:
                return False
            try:
                conn.execute(
                    """INSERT INTO signal_dlq (id, nonce, signal_type, body, reason, attempts, last_error)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()), row["nonce"], row["signal_type"], row["body"],
                        reason, row["attempts"], (error or "")[:500],
                    ),
                )
            except sqlite3.IntegrityError:
                # DLQ 已有同 nonce(重放中),保留
                pass
            conn.execute(
                "UPDATE signal_outbox SET status = 'dlq' WHERE nonce = ?", (nonce,)
            )
            return True

    def list_dlq(self, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM signal_dlq ORDER BY moved_at LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_dlq_by_nonce(self, nonce: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM signal_dlq WHERE nonce = ?", (nonce,)
            ).fetchone()
        return dict(row) if row else None

    def mark_dlq_replayed(self, nonce: str) -> None:
        """重放成功:DLQ 标 replayed_at(不删行,留审计痕迹)。"""
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE signal_dlq SET replayed_at = datetime('now') WHERE nonce = ?",
                (nonce,),
            )

    def get_user_by_openid(self, openid: str):
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE wechat_openid = ?", (openid,)).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str):
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_supabase_uid(self, supabase_uid: str):
        """Resolve a looma user by Supabase Auth user UUID (THOMAS unified identity)."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE supabase_uid = ?", (supabase_uid,)
            ).fetchone()
        return dict(row) if row else None

    def bind_supabase_to_user(self, user_id: str, supabase_uid: str):
        """Link a Supabase Auth UUID to an existing looma user (legacy account binding)."""
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE users SET supabase_uid = ?, updated_at = datetime('now') WHERE id = ?",
                (supabase_uid, user_id),
            )

    def get_or_create_user_by_supabase(self, supabase_uid: str, email: str = "",
                                       name: str = "", wechat_openid: str = None):
        """Find-or-create a looma user for a Supabase identity.

        1. supabase_uid 已映射 → 返回现有用户
        2. email 匹配存量用户（排除 thomas.local 占位邮箱）→ 绑定 supabase_uid（存量迁移）
        3. 否则创建新用户并绑定

        Returns (user_dict, created_bool).
        """
        user = self.get_user_by_supabase_uid(supabase_uid)
        if user:
            return user, False

        email = (email or "").strip().lower()
        if email and not email.endswith(".thomas.local"):
            legacy = self.get_user_by_email(email)
            if legacy:
                self.bind_supabase_to_user(legacy["id"], supabase_uid)
                if name and not legacy.get("name"):
                    with self.get_conn() as conn:
                        conn.execute(
                            "UPDATE users SET name = ?, updated_at = datetime('now') WHERE id = ?",
                            (name, legacy["id"]),
                        )
                return self.get_user_by_id(legacy["id"]), False

        user_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO users (id, email, email_hash, supabase_uid, wechat_openid, name)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, email or None, email_hash(email or None), supabase_uid,
                 wechat_openid, name),
            )
        return self.get_user_by_id(user_id), True

    def bind_wechat_to_user(self, user_id: str, wechat_openid: str):
        """Bind a WeChat openid to an existing user (cross-platform account linking)."""
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE users SET wechat_openid = ?, updated_at = datetime('now') WHERE id = ?",
                (wechat_openid, user_id)
            )

    # ============================================
    # Multi-identity management (overseas: Google/Apple/email)
    # ============================================
    def get_user_by_identity(self, provider: str, provider_uid: str):
        """Find a user by a third-party identity (google sub, apple sub, wechat openid)."""
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT u.* FROM users u
                   JOIN user_identities ui ON u.id = ui.user_id
                   WHERE ui.provider = ? AND ui.provider_uid = ?""",
                (provider, provider_uid)
            ).fetchone()
        return dict(row) if row else None

    def link_identity(self, user_id: str, provider: str, provider_uid: str,
                      provider_email: str = "", provider_name: str = "",
                      metadata_json: str = "{}"):
        """Link a third-party identity to an existing user.
        If the identity is already linked to a different user, raises ValueError."""
        with self.get_conn() as conn:
            existing = conn.execute(
                "SELECT user_id FROM user_identities WHERE provider = ? AND provider_uid = ?",
                (provider, provider_uid)
            ).fetchone()
            if existing and existing["user_id"] != user_id:
                raise ValueError(f"Identity {provider}:{provider_uid} is already linked to another user")
            if existing:
                return  # already linked to this user, idempotent
            conn.execute(
                """INSERT INTO user_identities (id, user_id, provider, provider_uid,
                   provider_email, provider_name, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, provider, provider_uid,
                 provider_email, provider_name, metadata_json)
            )

    def get_user_identities(self, user_id: str):
        """List all identities linked to a user."""
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT provider, provider_uid, provider_email, provider_name FROM user_identities WHERE user_id = ?",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_or_create_user_by_identity(self, provider: str, provider_uid: str,
                                       email: str = "", name: str = "",
                                       metadata_json: str = "{}"):
        """Find or create a user by third-party identity.
        If the identity exists, return the linked user.
        If not, create a new user + link the identity, return the new user.
        If email matches an existing user, link the identity to that user instead."""
        # 1. Check if identity already linked
        user = self.get_user_by_identity(provider, provider_uid)
        if user:
            return user, False  # existing user, not newly created

        # 2. Check if email matches an existing user (account merge)
        if email:
            user = self.get_user_by_email(email)
            if user:
                self.link_identity(user["id"], provider, provider_uid, email, name, metadata_json)
                return user, False

        # 3. Create new user + link identity
        user_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO users (id, email, email_hash, name) VALUES (?, ?, ?, ?)""",
                (user_id, email or None, email_hash(email or None), name)
            )
            conn.execute(
                """INSERT INTO user_identities (id, user_id, provider, provider_uid,
                   provider_email, provider_name, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, provider, provider_uid,
                 email, name, metadata_json)
            )
        return self.get_user_by_id(user_id), True  # newly created

    def update_user_tier(self, user_id: str, tier: str):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE users SET tier = ?, updated_at = datetime('now') WHERE id = ?",
                (tier, user_id)
            )

    # ============================================
    # Usage tracking (joint)
    # ============================================
    def log_usage(self, user_id: str, endpoint: str, tokens_used: int = 0):
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO usage_logs (id, user_id, endpoint, tokens_used)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, endpoint, tokens_used)
            )

    def get_daily_usage_count(self, user_id: str) -> int:
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM usage_logs
                   WHERE user_id = ? AND date(created_at) = date('now')""",
                (user_id,)
            ).fetchone()
        return row["cnt"] if row else 0

    # ============================================
    # LLM usage audit (joint) — 运维面 /v1/admin/llm-ops
    # ============================================
    def log_llm_usage(self, user_id, provider, model, tokens_in=0, tokens_out=0,
                      cost_yuan=0.0, latency_ms=0, status="ok", error=""):
        """Record one LLM call. user_id may be None (system/background calls)."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO llm_usage
                   (id, user_id, provider, model, tokens_in, tokens_out,
                    cost_yuan, latency_ms, status, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, provider, model,
                 int(tokens_in or 0), int(tokens_out or 0),
                 float(cost_yuan or 0.0), int(latency_ms or 0),
                 status, (error or "")[:500]),
            )

    def get_llm_usage_stats(self, hours: int = 24):
        """Aggregated LLM usage over the window: totals, latency, cost, top models/users."""
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS cnt,
                          AVG(latency_ms) AS avg_ms,
                          SUM(cost_yuan) AS cost,
                          SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors,
                          SUM(tokens_in) AS tin,
                          SUM(tokens_out) AS tout

                   FROM llm_usage
                   WHERE created_at >= datetime('now', ?)""",
                (f"-{hours} hours",),
            ).fetchone()
            top_models = [
                dict(r) for r in conn.execute(
                    """SELECT provider, model, COUNT(*) AS calls, SUM(cost_yuan) AS cost
                       FROM llm_usage
                       WHERE created_at >= datetime('now', ?)
                       GROUP BY provider, model ORDER BY calls DESC LIMIT 6""",
                    (f"-{hours} hours",),
                ).fetchall()
            ]
            top_users = [
                dict(r) for r in conn.execute(
                    """SELECT user_id, COUNT(*) AS calls, SUM(cost_yuan) AS cost
                       FROM llm_usage
                       WHERE user_id IS NOT NULL
                         AND created_at >= datetime('now', ?)
                       GROUP BY user_id ORDER BY calls DESC LIMIT 6""",
                    (f"-{hours} hours",),
                ).fetchall()
            ]
        calls = row["cnt"] or 0
        return {
            "hours": hours,
            "calls": calls,
            "avg_latency_ms": round(row["avg_ms"] or 0),
            "total_cost_yuan": round(row["cost"] or 0.0, 2),
            "tokens_in": row["tin"] or 0,
            "tokens_out": row["tout"] or 0,
            "error_rate": round((row["errors"] or 0) / max(calls, 1), 4),
            "top_models": top_models,
            "top_users": top_users,
        }

    # ============================================
    # Game profile operations (Jason)
    # ============================================
    def upsert_game_profile(self, user_id: str, personality_type: str, personality_detail: str = ""):
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO game_profiles (id, user_id, personality_type, personality_detail)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     personality_type = excluded.personality_type,
                     personality_detail = excluded.personality_detail,
                     updated_at = datetime('now')""",
                (str(uuid.uuid4()), user_id, personality_type, personality_detail)
            )

    def update_game_identity(self, user_id: str, identity: str):
        """Persist PlanetX onboarding identity (explorer | captain | wanderer)."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM game_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE game_profiles SET identity = ?, updated_at = datetime('now')
                       WHERE user_id = ?""",
                    (identity, user_id),
                )
            else:
                conn.execute(
                    """INSERT INTO game_profiles (id, user_id, identity)
                       VALUES (?, ?, ?)""",
                    (str(uuid.uuid4()), user_id, identity),
                )

    def get_game_profile(self, user_id: str):
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM game_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_game_profiles_for_users(self, user_ids: list):
        """Batch-fetch game profiles joined with display name for fleet matching."""
        if not user_ids:
            return []
        placeholders = ",".join("?" * len(user_ids))
        with self.get_conn() as conn:
            rows = conn.execute(
                f"""SELECT gp.*, u.name AS display_name
                    FROM game_profiles gp
                    JOIN users u ON u.id = gp.user_id
                    WHERE gp.user_id IN ({placeholders})""",
                tuple(user_ids),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_xp(self, user_id: str, xp_amount: int):
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE game_profiles SET xp = xp + ?, updated_at = datetime('now')
                   WHERE user_id = ?""",
                (xp_amount, user_id)
            )

    def update_level(self, user_id: str, level: int):
        """Update the user's game level."""
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE game_profiles SET level = ?, updated_at = datetime('now')
                   WHERE user_id = ?""",
                (level, user_id)
            )

    # ============================================
    # Fleet operations (Jason)
    # ============================================
    def create_fleet(self, captain_id: str, name: str, description: str = ""):
        """Create a new fleet. Captain is auto-added as first member.
        Generates a unique 8-char invite_code for sharing."""
        fleet_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())
        invite_code = str(uuid.uuid4())[:8].upper()
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO fleets (id, name, captain_id, description, invite_code)
                   VALUES (?, ?, ?, ?, ?)""",
                (fleet_id, name, captain_id, description, invite_code)
            )
            conn.execute(
                """INSERT INTO fleet_members (id, fleet_id, user_id)
                   VALUES (?, ?, ?)""",
                (member_id, fleet_id, captain_id)
            )
        return fleet_id

    def get_fleet_by_invite_code(self, invite_code: str):
        """Look up a fleet by its invite_code."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM fleets WHERE invite_code = ?", (invite_code.upper(),)
            ).fetchone()
        return dict(row) if row else None

    def get_fleet_by_id(self, fleet_id: str):
        """Get fleet details by ID."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM fleets WHERE id = ?", (fleet_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_fleet(self, user_id: str):
        """Get the fleet the user belongs to (one fleet per user in MVP)."""
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT f.* FROM fleets f
                   JOIN fleet_members fm ON f.id = fm.fleet_id
                   WHERE fm.user_id = ?""",
                (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_fleet_members(self, fleet_id: str):
        """Get all members of a fleet."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT fm.id, fm.fleet_id, fm.user_id, fm.joined_at,
                          u.name, u.email
                   FROM fleet_members fm
                   JOIN users u ON fm.user_id = u.id
                   WHERE fm.fleet_id = ?""",
                (fleet_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def join_fleet(self, fleet_id: str, user_id: str):
        """Add a user to a fleet. Raises if fleet doesn't exist or user already in one."""
        member_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            # Verify fleet exists
            fleet = conn.execute(
                "SELECT id FROM fleets WHERE id = ?", (fleet_id,)
            ).fetchone()
            if not fleet:
                raise ValueError(f"Fleet {fleet_id} does not exist")

            # Check user not already in a fleet (MVP: one fleet per user)
            existing = conn.execute(
                """SELECT fm.fleet_id FROM fleet_members fm
                   WHERE fm.user_id = ?""",
                (user_id,)
            ).fetchone()
            if existing:
                raise ValueError(
                    f"User {user_id} already in fleet {existing['fleet_id']}"
                )

            conn.execute(
                """INSERT INTO fleet_members (id, fleet_id, user_id)
                   VALUES (?, ?, ?)""",
                (member_id, fleet_id, user_id)
            )

    def leave_fleet(self, user_id: str):
        """Remove a user from their fleet. Captain cannot leave (must dissolve)."""
        with self.get_conn() as conn:
            # Find user's current fleet
            membership = conn.execute(
                """SELECT fm.fleet_id, fm.user_id FROM fleet_members fm
                   WHERE fm.user_id = ?""",
                (user_id,)
            ).fetchone()
            if not membership:
                return  # User not in any fleet, nothing to do

            fleet_id = membership["fleet_id"]

            # Check if user is captain — captain cannot leave, must dissolve
            fleet = conn.execute(
                "SELECT captain_id FROM fleets WHERE id = ?", (fleet_id,)
            ).fetchone()
            if fleet and fleet["captain_id"] == user_id:
                raise ValueError("Captain cannot leave fleet; dissolve the fleet instead")

            conn.execute(
                "DELETE FROM fleet_members WHERE user_id = ? AND fleet_id = ?",
                (user_id, fleet_id)
            )

    def dissolve_fleet(self, fleet_id: str, captain_id: str):
        """Dissolve a fleet. Only the captain can dissolve. Removes all members."""
        with self.get_conn() as conn:
            fleet = conn.execute(
                "SELECT * FROM fleets WHERE id = ?", (fleet_id,)
            ).fetchone()
            if not fleet:
                raise ValueError(f"Fleet {fleet_id} does not exist")
            if fleet["captain_id"] != captain_id:
                raise ValueError("Only the captain can dissolve the fleet")

            conn.execute(
                "DELETE FROM fleet_members WHERE fleet_id = ?", (fleet_id,)
            )
            conn.execute(
                "DELETE FROM fleets WHERE id = ?", (fleet_id,)
            )

    def get_fleet_member_count(self, fleet_id: str) -> int:
        """Get number of members in a fleet."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM fleet_members WHERE fleet_id = ?",
                (fleet_id,)
            ).fetchone()
        return row["cnt"] if row else 0

    # ============================================
    # Mission operations (Jason)
    # ============================================
    def complete_mission(self, user_id: str, mission_id: str, xp_reward: int = 0):
        """Record a mission completion. Returns (completion_id, was_new).
        If user already completed this mission, returns (None, False) — no double reward."""
        completion_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO mission_completions (id, user_id, mission_id, xp_reward)
                       VALUES (?, ?, ?, ?)""",
                    (completion_id, user_id, mission_id, xp_reward)
                )
            except sqlite3.IntegrityError:
                # UNIQUE(user_id, mission_id) — already completed
                return None, False

            # Award XP to game profile
            if xp_reward > 0:
                conn.execute(
                    """UPDATE game_profiles SET xp = xp + ?, updated_at = datetime('now')
                       WHERE user_id = ?""",
                    (xp_reward, user_id)
                )

        return completion_id, True

    def get_user_missions(self, user_id: str):
        """Get all missions completed by a user."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT mc.id, mc.mission_id, mc.xp_reward, mc.completed_at
                   FROM mission_completions mc
                   WHERE mc.user_id = ?
                   ORDER BY mc.completed_at DESC""",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def count_spread_signals(self, user_id: str) -> int:
        """Count invitees who used this user's referral code AND completed personality.

        Design (ENGINEERING_CLOSED_LOOP_P0): count only after first mission to reduce spam.
        Excludes profile_share codes.
        """
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(DISTINCT ic.used_by) AS cnt
                   FROM invite_codes ic
                   INNER JOIN mission_completions mc
                     ON mc.user_id = ic.used_by AND mc.mission_id = 'personality'
                   WHERE ic.created_by = ?
                     AND ic.used_by IS NOT NULL
                     AND IFNULL(ic.tier_grant, '') != 'profile_share'""",
                (user_id,),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    # ============================================
    # Match consensus (PlanetX phase-2)
    # ============================================
    def create_match_consensus(
        self,
        *,
        fleet_id: str,
        initiator_id: str,
        candidate_id: str,
        match_score: int,
        reason: str = "",
        expires_hours: int = 72,
    ) -> dict:
        """Create or refresh a pending consensus between initiator and candidate."""
        import uuid as _uuid
        from datetime import datetime, timedelta, timezone

        consensus_id = str(_uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=expires_hours)).strftime("%Y-%m-%d %H:%M:%S")

        with self.get_conn() as conn:
            # Reuse open pending pair if still valid
            existing = conn.execute(
                """SELECT * FROM match_consensus
                   WHERE initiator_id = ? AND candidate_id = ? AND status = 'pending'
                     AND expires_at > datetime('now')
                   ORDER BY created_at DESC LIMIT 1""",
                (initiator_id, candidate_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE match_consensus
                       SET match_score = ?, reason = ?, fleet_id = ?, expires_at = ?
                       WHERE id = ?""",
                    (match_score, reason, fleet_id, expires_at, existing["id"]),
                )
                row = conn.execute(
                    "SELECT * FROM match_consensus WHERE id = ?", (existing["id"],)
                ).fetchone()
                return dict(row)

            conn.execute(
                """INSERT INTO match_consensus
                   (id, fleet_id, initiator_id, candidate_id, match_score, status, reason, expires_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    consensus_id,
                    fleet_id,
                    initiator_id,
                    candidate_id,
                    match_score,
                    reason,
                    expires_at,
                ),
            )
            row = conn.execute(
                "SELECT * FROM match_consensus WHERE id = ?", (consensus_id,)
            ).fetchone()
        return dict(row)

    def get_match_consensus(self, consensus_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM match_consensus WHERE id = ?", (consensus_id,)
            ).fetchone()
        return dict(row) if row else None

    def acknowledge_match_consensus(
        self, consensus_id: str, actor_id: str, action: str = "accept"
    ) -> tuple[dict | None, str | None]:
        """Candidate (or either party) accepts/rejects. Returns (row, error_code)."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM match_consensus WHERE id = ?", (consensus_id,)
            ).fetchone()
            if not row:
                return None, "not_found"
            rec = dict(row)
            if rec["status"] == "verified":
                return rec, None
            if rec["status"] in ("rejected", "expired"):
                return None, "not_pending"
            # Expire stale
            expired = conn.execute(
                """SELECT 1 FROM match_consensus
                   WHERE id = ? AND expires_at <= datetime('now')""",
                (consensus_id,),
            ).fetchone()
            if expired:
                conn.execute(
                    "UPDATE match_consensus SET status = 'expired' WHERE id = ?",
                    (consensus_id,),
                )
                return None, "expired"
            if actor_id not in (rec["initiator_id"], rec["candidate_id"]):
                return None, "forbidden"
            # Prefer candidate acknowledgement; initiator may also accept for demo
            if action == "reject":
                conn.execute(
                    "UPDATE match_consensus SET status = 'rejected' WHERE id = ?",
                    (consensus_id,),
                )
            else:
                conn.execute(
                    """UPDATE match_consensus
                       SET status = 'verified', verified_at = datetime('now')
                       WHERE id = ?""",
                    (consensus_id,),
                )
            updated = conn.execute(
                "SELECT * FROM match_consensus WHERE id = ?", (consensus_id,)
            ).fetchone()
        return (dict(updated) if updated else None), None

    def list_match_consensus_for_user(self, user_id: str) -> list[dict]:
        with self.get_conn() as conn:
            # Auto-expire
            conn.execute(
                """UPDATE match_consensus SET status = 'expired'
                   WHERE status = 'pending' AND expires_at <= datetime('now')"""
            )
            rows = conn.execute(
                """SELECT * FROM match_consensus
                   WHERE initiator_id = ? OR candidate_id = ?
                   ORDER BY created_at DESC LIMIT 50""",
                (user_id, user_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def has_verified_match_consensus(self, user_id: str) -> bool:
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT 1 FROM match_consensus
                   WHERE status = 'verified'
                     AND (initiator_id = ? OR candidate_id = ?)
                   LIMIT 1""",
                (user_id, user_id),
            ).fetchone()
        return row is not None

    def is_mission_completed(self, user_id: str, mission_id: str) -> bool:
        """Check if a user has already completed a specific mission."""
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT id FROM mission_completions
                   WHERE user_id = ? AND mission_id = ?""",
                (user_id, mission_id)
            ).fetchone()
        return row is not None

    # ============================================
    # Trust Layer: trust_memories (append-only)
    # ============================================
    def insert_trust_memory(self, user_id: str, session_type: str,
                            session_id: str, memory_content: dict,
                            memory_level: int = 1) -> str:
        """Insert an append-only trust memory. Returns memory_id."""
        memory_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO trust_memories
                   (id, user_id, session_type, session_id, memory_content, memory_level)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (memory_id, user_id, session_type, session_id,
                 json.dumps(memory_content, ensure_ascii=False), memory_level),
            )
        return memory_id

    def get_trust_memories(self, user_id: str,
                           session_type: str | None = None,
                           limit: int = 50) -> list[dict]:
        """Retrieve trust memories for a user, optionally filtered by type."""
        if session_type:
            sql = """SELECT * FROM trust_memories
                     WHERE user_id = ? AND session_type = ?
                     ORDER BY created_at DESC LIMIT ?"""
            params = (user_id, session_type, limit)
        else:
            sql = """SELECT * FROM trust_memories
                     WHERE user_id = ?
                     ORDER BY created_at DESC LIMIT ?"""
            params = (user_id, limit)
        with self.get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ============================================
    # Trust Layer: trust_attestations
    # ============================================
    def upsert_trust_attestation(self, candidate_id: str, claim_type: str,
                                 claim_statement: str, evidence_type: str,
                                 verification_status: str = "unverified",
                                 evidence_refs: list | None = None,
                                 confidence_score: float = 0.0) -> dict:
        """Upsert a trust attestation claim card. Returns the attestation dict.
        One row per (candidate_id, claim_type) — subsequent calls update the same row."""
        attestation_id = str(uuid.uuid4())
        refs_json = json.dumps(evidence_refs or [])
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO trust_attestations
                   (id, candidate_id, claim_type, claim_statement, evidence_type,
                    verification_status, evidence_refs, confidence_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(candidate_id, claim_type) DO UPDATE SET
                     claim_statement = excluded.claim_statement,
                     verification_status = excluded.verification_status,
                     evidence_refs = excluded.evidence_refs,
                     confidence_score = excluded.confidence_score,
                     updated_at = datetime('now')""",
                (attestation_id, candidate_id, claim_type, claim_statement,
                 evidence_type, verification_status, refs_json, confidence_score),
            )
            row = conn.execute(
                """SELECT * FROM trust_attestations
                   WHERE candidate_id = ? AND claim_type = ?""",
                (candidate_id, claim_type),
            ).fetchone()
        return dict(row) if row else {}

    def get_trust_attestations(self, candidate_id: str) -> list[dict]:
        """Get all attestation cards for a candidate."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM trust_attestations
                   WHERE candidate_id = ?
                   ORDER BY created_at DESC""",
                (candidate_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_trust_attestation(self, attestation_id: str) -> dict | None:
        """Get a single attestation by ID."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM trust_attestations WHERE id = ?", (attestation_id,),
            ).fetchone()
        return dict(row) if row else None

    # ============================================
    # Quota operations (joint)
    # ============================================
    def get_trust_attestations_by_type(self, candidate_id: str, claim_types: list[str] | None = None) -> list[dict]:
        """Get attestations for candidate, optionally filtered by claim_type."""
        if claim_types:
            placeholders = ",".join("?" * len(claim_types))
            sql = f"""SELECT * FROM trust_attestations
                      WHERE candidate_id = ? AND claim_type IN ({placeholders})
                      ORDER BY created_at DESC"""
            params = [candidate_id] + claim_types
        else:
            sql = """SELECT * FROM trust_attestations
                     WHERE candidate_id = ? ORDER BY created_at DESC"""
            params = [candidate_id]
        with self.get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def update_attestation_signature(self, attestation_id: str, signature: str, expires_at: str) -> bool:
        """Set the Ed25519 signature and expiration on an attestation."""
        with self.get_conn() as conn:
            cur = conn.execute(
                """UPDATE trust_attestations
                   SET signature = ?, expires_at = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (signature, expires_at, attestation_id),
            )
        return cur.rowcount > 0

    # ============================================
    # Trust Layer: share_codes
    # ============================================
    def create_share_code(self, owner_id: str, scope: list[str],
                          max_access_count: int = 10,
                          expires_in_seconds: int = 604800) -> dict:
        """Generate a temporary share code for third-party verification.
        
        Args:
            owner_id: candidate user_id
            scope: list of claim_types (e.g. ['identity', 'collaboration'])
            max_access_count: max times this code can be used (default 10)
            expires_in_seconds: TTL in seconds (default 604800 = 7 days, max 2592000 = 30 days)
        """
        import secrets
        from datetime import datetime, timedelta, timezone

        _SHA_TZ = timezone(timedelta(hours=8))
        now = datetime.now(_SHA_TZ)
        expires_at = (now + timedelta(seconds=min(expires_in_seconds, 2592000))).isoformat()

        code_id = str(uuid.uuid4())
        code = "sc_" + secrets.token_hex(8)

        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO share_codes
                   (id, code, owner_id, scope, max_access_count, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (code_id, code, owner_id, json.dumps(scope), max_access_count, expires_at),
            )
            row = conn.execute(
                "SELECT * FROM share_codes WHERE id = ?", (code_id,),
            ).fetchone()
        result = dict(row) if row else {}
        if "scope" in result and isinstance(result["scope"], str):
            result["scope"] = json.loads(result["scope"])
        return result

    def get_share_code(self, code: str) -> dict | None:
        """Look up a share_code by its code string."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM share_codes WHERE code = ?", (code,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        if "scope" in result and isinstance(result["scope"], str):
            result["scope"] = json.loads(result["scope"])
        return result

    def consume_share_code(self, code: str) -> dict | None:
        """Increment access_count for a share_code. Returns updated row or None if exhausted/expired."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM share_codes WHERE code = ? AND status = 'active'", (code,),
            ).fetchone()
            if not row:
                return None

            sc = dict(row)
            # Check expiration
            from datetime import datetime, timezone, timedelta
            _SHA_TZ = timezone(timedelta(hours=8))
            now = datetime.now(_SHA_TZ).isoformat()
            if sc["expires_at"] < now:
                conn.execute(
                    "UPDATE share_codes SET status = 'expired' WHERE code = ?", (code,),
                )
                return None

            # Check exhausted
            if sc["access_count"] >= sc["max_access_count"]:
                return None

            conn.execute(
                "UPDATE share_codes SET access_count = access_count + 1 WHERE code = ?",
                (code,),
            )
            row2 = conn.execute(
                "SELECT * FROM share_codes WHERE code = ?", (code,),
            ).fetchone()
        result = dict(row2) if row2 else {}
        if "scope" in result and isinstance(result["scope"], str):
            result["scope"] = json.loads(result["scope"])
        return result

    def revoke_share_code(self, code_id: str, owner_id: str) -> bool:
        """Revoke a share_code (owner only)."""
        with self.get_conn() as conn:
            cur = conn.execute(
                """UPDATE share_codes SET status = 'revoked'
                   WHERE id = ? AND owner_id = ? AND status = 'active'""",
                (code_id, owner_id),
            )
        return cur.rowcount > 0

    def list_share_codes(self, owner_id: str) -> list[dict]:
        """List all share codes for an owner."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM share_codes
                   WHERE owner_id = ?
                   ORDER BY created_at DESC""",
                (owner_id,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if "scope" in d and isinstance(d["scope"], str):
                d["scope"] = json.loads(d["scope"])
            results.append(d)
        return results

    # ============================================
    # Trust Layer: verification_audit_log
    # ============================================
    def insert_verification_audit(self, share_code: str, owner_id: str,
                                  verifier_info: str, attestation_ids: list[str],
                                  result: str = "success") -> str:
        """Log a third-party verification access. Returns audit log ID."""
        log_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO verification_audit_log
                   (id, share_code, owner_id, verifier_info, attestation_ids, result)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (log_id, share_code, owner_id, verifier_info,
                 json.dumps(attestation_ids), result),
            )
        return log_id

    def get_verification_audit_log(self, owner_id: str, limit: int = 50) -> list[dict]:
        """Get verification audit trail for a candidate."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM verification_audit_log
                   WHERE owner_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (owner_id, limit),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if "attestation_ids" in d and isinstance(d["attestation_ids"], str):
                d["attestation_ids"] = json.loads(d["attestation_ids"])
            results.append(d)
        return results

    def get_quota(self, user_id: str, resource: str, date: str):
        """Get quota record for a specific user + resource + date."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM quota_records WHERE user_id=? AND resource=? AND date=?",
                (user_id, resource, date),
            ).fetchone()
        return dict(row) if row else None

    def consume_quota(self, user_id: str, resource: str, date: str, limit: int) -> bool:
        """Consume 1 quota unit. Returns True=success, False=exceeded."""
        with self.get_conn() as conn:
            existing = conn.execute(
                "SELECT used FROM quota_records WHERE user_id=? AND resource=? AND date=?",
                (user_id, resource, date),
            ).fetchone()
            if existing:
                used = existing[0]
                if used >= limit:
                    return False
                conn.execute(
                    "UPDATE quota_records SET used=used+1 WHERE user_id=? AND resource=? AND date=?",
                    (user_id, resource, date),
                )
            else:
                conn.execute(
                    "INSERT INTO quota_records (user_id, resource, date, used, daily_limit) VALUES (?, ?, ?, 1, ?)",
                    (user_id, resource, date, limit),
                )
        return True

    def refund_quota(self, user_id: str, resource: str, date: str) -> bool:
        """Refund 1 daily quota unit (best-effort). Returns True if decremented."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT used FROM quota_records WHERE user_id=? AND resource=? AND date=?",
                (user_id, resource, date),
            ).fetchone()
            if not row or row[0] <= 0:
                return False
            conn.execute(
                "UPDATE quota_records SET used=used-1 WHERE user_id=? AND resource=? AND date=? AND used>0",
                (user_id, resource, date),
            )
        return True

    # ============================================
    # Boost pack operations (joint)
    # ============================================
    def create_boost_pack(self, user_id: str, pack_name: str, credits: int,
                          price_yuan: int = 29, days_valid: int = 30) -> int:
        """Create a boost pack for a user."""
        from datetime import timedelta
        now = _dt_now()
        expires = (now + timedelta(days=days_valid)).isoformat()
        with self.get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO boost_packs (user_id, pack_name, credits, credits_used, price_yuan, purchased_at, expires_at, status)
                   VALUES (?, ?, ?, 0, ?, ?, ?, 'active')""",
                (user_id, pack_name, credits, price_yuan, now.isoformat(), expires),
            )
        return cursor.lastrowid or 0

    def get_boost_credit_remaining(self, user_id: str) -> int:
        """Get total remaining boost credits for a user."""
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(credits - credits_used), 0) AS remaining
                   FROM boost_packs
                   WHERE user_id=? AND status='active'
                     AND expires_at > datetime('now')""",
                (user_id,),
            ).fetchone()
        return row[0] if row else 0

    def consume_boost_credit(self, user_id: str, resource: str) -> bool:
        """Consume 1 boost credit from the earliest-expiring active pack."""
        with self.get_conn() as conn:
            pack = conn.execute(
                """SELECT * FROM boost_packs
                   WHERE user_id=? AND status='active'
                     AND expires_at > datetime('now')
                     AND credits_used < credits
                   ORDER BY expires_at ASC LIMIT 1""",
                (user_id,),
            ).fetchone()

            if not pack:
                return False

            pack_dict = dict(pack)
            pack_id = pack_dict["id"]

            conn.execute(
                "UPDATE boost_packs SET credits_used=credits_used+1 WHERE id=?",
                (pack_id,),
            )
            conn.execute(
                "INSERT INTO boost_consumptions (user_id, boost_pack_id, resource, credits_consumed) VALUES (?, ?, ?, 1)",
                (user_id, pack_id, resource),
            )
            if pack_dict["credits_used"] + 1 >= pack_dict["credits"]:
                conn.execute("UPDATE boost_packs SET status='exhausted' WHERE id=?", (pack_id,))
        return True

    # ============================================
    # Poetry operations (Jason)
    # ============================================
    def insert_poem(self, title: str, author: str = "", dynasty: str = "",
                    theme: str = "", content: str = "", tags: str = "",
                    source: str = "imported") -> int:
        """Insert a single poem. Returns the row id."""
        with self.get_conn() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO poems (title, author, dynasty, theme, content, tags, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, author, dynasty, theme, content, tags, source)
            )
        return cursor.lastrowid or 0

    def bulk_insert_poems(self, poems: list[dict]) -> int:
        """Bulk insert poems from a list of dicts.
        Each dict must have: title, content. Optional: author, dynasty, theme, tags.
        Returns count of inserted rows."""
        inserted = 0
        with self.get_conn() as conn:
            for p in poems:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO poems (title, author, dynasty, theme, content, tags, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (p.get("title", ""), p.get("author", ""), p.get("dynasty", ""),
                         p.get("theme", ""), p.get("content", ""), p.get("tags", ""),
                         p.get("source", "imported"))
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass  # duplicate title, skip
        return inserted

    def get_poem_by_id(self, poem_id: int):
        """Get a single poem by id."""
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM poems WHERE id = ?", (poem_id,)).fetchone()
        return dict(row) if row else None

    def get_poems(self, dynasty: str | None = None, author: str | None = None,
                  theme: str | None = None, keyword: str | None = None,
                  page: int = 1, per_page: int = 20) -> dict:
        """Browse/filter poems with pagination.
        Returns {items: [...], total: N, page: P, per_page: PP}."""
        clauses = []
        params = []
        if dynasty:
            clauses.append("dynasty = ?")
            params.append(dynasty)
        if author:
            clauses.append("author = ?")
            params.append(author)
        if theme:
            clauses.append("theme = ?")
            params.append(theme)
        if keyword:
            clauses.append("(title LIKE ? OR content LIKE ? OR author LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

        where = " AND ".join(clauses) if clauses else ""
        where_sql = f"WHERE {where}" if where else ""

        # Count
        with self.get_conn() as conn:
            count_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM poems {where_sql}", params
            ).fetchone()
            total = count_row["cnt"] if count_row else 0

            # Paginate
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""SELECT id, title, author, dynasty, theme,
                           SUBSTR(content, 1, 80) as content_preview, tags
                    FROM poems {where_sql}
                    ORDER BY id ASC
                    LIMIT ? OFFSET ?""",
                params + [per_page, offset]
            ).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def get_random_poems(self, count: int = 3):
        """Get random poems for discovery mode."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, title, author, dynasty, theme,
                          SUBSTR(content, 1, 120) as content_preview
                   FROM poems
                   ORDER BY RANDOM()
                   LIMIT ?""",
                (count,)
            ).fetchall()
        return [dict(r) for r in rows]

    def count_poems(self) -> int:
        """Total poem count."""
        with self.get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM poems").fetchone()
        return row["cnt"] if row else 0

    # ============================================
    # Poetry challenge (信达雅)
    # ============================================

    @staticmethod
    def _iso_week_key(dt=None) -> str:
        from datetime import datetime, timezone
        d = dt or datetime.now(timezone.utc)
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    @staticmethod
    def _week_bounds_utc(dt=None):
        """Return (starts_at, ends_at) ISO strings for the UTC ISO week containing dt."""
        from datetime import datetime, timedelta, timezone
        d = dt or datetime.now(timezone.utc)
        # Monday 00:00 UTC → next Monday 00:00 UTC
        monday = (d - timedelta(days=d.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        next_monday = monday + timedelta(days=7)
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return monday.strftime(fmt), next_monday.strftime(fmt)

    def pick_short_poem_for_challenge(self, max_chars: int = 80):
        """Prefer short classical poems suitable for weekly translation."""
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT id, title, author, dynasty, theme, content, tags
                   FROM poems
                   WHERE LENGTH(content) > 0 AND LENGTH(content) <= ?
                   ORDER BY RANDOM()
                   LIMIT 1""",
                (max_chars,),
            ).fetchone()
            if row:
                return dict(row)
            # Fallback: any poem
            row = conn.execute(
                """SELECT id, title, author, dynasty, theme, content, tags
                   FROM poems
                   ORDER BY RANDOM()
                   LIMIT 1"""
            ).fetchone()
        return dict(row) if row else None

    def get_challenge_round_by_week(self, week_key: str):
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM challenge_rounds WHERE week_key = ?",
                (week_key,),
            ).fetchone()
        return dict(row) if row else None

    def get_open_challenge_round(self):
        """Current open round whose ends_at is still in the future (UTC)."""
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM challenge_rounds
                   WHERE status = 'open' AND ends_at > datetime('now')
                   ORDER BY starts_at DESC
                   LIMIT 1"""
            ).fetchone()
        return dict(row) if row else None

    def create_challenge_round(self, week_key: str, poem_id: int, title: str,
                               starts_at: str, ends_at: str):
        with self.get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO challenge_rounds
                   (week_key, poem_id, title, status, starts_at, ends_at)
                   VALUES (?, ?, ?, 'open', ?, ?)""",
                (week_key, poem_id, title, starts_at, ends_at),
            )
            return cur.lastrowid

    def ensure_current_challenge_round(self) -> dict | None:
        """Return this week's open round, creating one from a short poem if needed.

        Returns None when the poems library is empty (cannot seed a round).
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        week_key = self._iso_week_key(now)

        existing = self.get_challenge_round_by_week(week_key)
        if existing:
            # Auto-close stale rounds from previous weeks still marked open
            if existing.get("status") == "open" and existing.get("ends_at", "") <= now.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ):
                with self.get_conn() as conn:
                    conn.execute(
                        "UPDATE challenge_rounds SET status = 'closed' WHERE id = ?",
                        (existing["id"],),
                    )
                existing["status"] = "closed"
            else:
                return existing

        # Close any other lingering open rounds
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE challenge_rounds SET status = 'closed'
                   WHERE status = 'open' AND week_key != ?""",
                (week_key,),
            )

        poem = self.pick_short_poem_for_challenge()
        if not poem:
            return None

        starts_at, ends_at = self._week_bounds_utc(now)
        title = f"Xin-Da-Ya · {poem.get('title', '')}"
        round_id = self.create_challenge_round(
            week_key=week_key,
            poem_id=poem["id"],
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        return self.get_challenge_round_by_week(week_key) or {
            "id": round_id,
            "week_key": week_key,
            "poem_id": poem["id"],
            "title": title,
            "status": "open",
            "starts_at": starts_at,
            "ends_at": ends_at,
        }

    def get_challenge_entry(self, round_id: int, user_id: str):
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM challenge_entries
                   WHERE round_id = ? AND user_id = ?""",
                (round_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def upsert_challenge_entry(
        self,
        round_id: int,
        user_id: str,
        translation: str,
        note: str = "",
        license_accepted: bool = False,
    ):
        """Create or update the user's single entry for a round. Returns entry dict."""
        existing = self.get_challenge_entry(round_id, user_id)
        with self.get_conn() as conn:
            if existing:
                conn.execute(
                    """UPDATE challenge_entries
                       SET translation = ?, note = ?, license_accepted = ?,
                           updated_at = datetime('now')
                       WHERE id = ?""",
                    (
                        translation,
                        note,
                        1 if license_accepted else 0,
                        existing["id"],
                    ),
                )
                entry_id = existing["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO challenge_entries
                       (round_id, user_id, translation, note, license_accepted)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        round_id,
                        user_id,
                        translation,
                        note,
                        1 if license_accepted else 0,
                    ),
                )
                entry_id = cur.lastrowid
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM challenge_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_poetry_stats(self) -> dict:
        """Get poetry collection stats: total, dynasty distribution, theme distribution."""
        with self.get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM poems").fetchone()["cnt"]
            dynasties = conn.execute(
                "SELECT dynasty, COUNT(*) as cnt FROM poems GROUP BY dynasty ORDER BY cnt DESC LIMIT 20"
            ).fetchall()
            themes = conn.execute(
                "SELECT theme, COUNT(*) as cnt FROM poems GROUP BY theme ORDER BY cnt DESC LIMIT 20"
            ).fetchall()
        return {
            "total": total,
            "dynasties": [{"name": r["dynasty"], "count": r["cnt"]} for r in dynasties],
            "themes": [{"name": r["theme"], "count": r["cnt"]} for r in themes],
        }

    def get_authors(self, dynasty: str | None = None,
                    page: int = 1, per_page: int = 24) -> dict:
        """List distinct authors with poem counts, sorted by count desc.
        Returns {items: [{name, dynasty, count}], total: N, page: P, per_page: PP}."""
        clauses = []
        params = []
        if dynasty:
            clauses.append("dynasty = ?")
            params.append(dynasty)

        where = " AND ".join(clauses) if clauses else ""
        where_sql = f"WHERE {where}" if where else ""
        count_where = f"WHERE author != ''" + (f" AND {where}" if where else "")

        with self.get_conn() as conn:
            count_row = conn.execute(
                f"SELECT COUNT(DISTINCT author) as cnt FROM poems {count_where}", params
            ).fetchone()
            total = count_row["cnt"] if count_row else 0

            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""SELECT author as name, dynasty,
                           COUNT(*) as count
                    FROM poems {where_sql}
                    WHERE author != ''
                    GROUP BY author
                    ORDER BY count DESC
                    LIMIT ? OFFSET ?""",
                params + [per_page, offset]
            ).fetchall()

        return {
            "items": [{"name": r["name"], "dynasty": r["dynasty"], "count": r["count"]} for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    # ============================================
    # Document operations (szbenyx)
    # ============================================
    def register_document(self, title: str, file_path: str, doc_type: str,
                          file_size: int = 0, metadata: dict | None = None) -> int:
        """Register a new document for processing."""
        with self.get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO documents (title, file_path, doc_type, file_size, metadata, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
                (title, file_path, doc_type, file_size, json.dumps(metadata or {}),
                 _dt_now().isoformat())
            )
        return cursor.lastrowid or 0

    def update_document_status(self, doc_id: int, status: str, chunk_count: int = 0):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE documents SET status=?, chunk_count=?, processed_at=? WHERE id=?",
                (status, chunk_count, _dt_now().isoformat(), doc_id)
            )

    def get_documents(self, status: str | None = None):
        with self.get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE status=? ORDER BY created_at DESC", (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    # ============================================
    # Query log operations (joint — data flywheel)
    # ============================================
    def log_query(self, query_text: str, provider: str, response_time_ms: float,
                  chunk_count: int = 0, user_id: str | None = None,
                  intent_label: str | None = None):
        """Log a query for the data flywheel."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO query_logs (query_text, provider, response_time_ms, chunk_count, user_id, intent_label, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (query_text, provider, response_time_ms, chunk_count, user_id, intent_label,
                 _dt_now().isoformat())
            )

    # ============================================
    # Seed: beta users
    # ============================================
    def seed_beta_users(self) -> list[str]:
        """Seed a set of beta test users with pre-assigned tiers.
        Only inserts users that don't already exist (by email / wechat_openid).
        Returns list of created user IDs.

        Creates:
          - beta_free@looma.test       (tier=free,   early_adopter)
          - beta_supporter@looma.test  (tier=supporter, early_adopter)
          - beta_pro@looma.test        (tier=pro,     early_adopter)
          - beta_admin@looma.test      (tier=pro,     early_adopter, role=admin)
        """
        import bcrypt

        created = []
        with self.get_conn() as conn:
            for u in BETA_USERS:
                # Check if already exists (by email)
                existing = conn.execute(
                    "SELECT id FROM users WHERE email = ?", (u["email"],)
                ).fetchone()
                if existing:
                    continue

                user_id = str(uuid.uuid4())
                # Dev-only: use a simple password for test accounts
                password_hash = bcrypt.hashpw(
                    "looma123".encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")

                conn.execute(
                    """INSERT INTO users (id, email, email_hash, password_hash, name, tier, role, is_early_adopter)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        u["email"],
                        email_hash(u["email"]),
                        password_hash,
                        u["name"],
                        u["tier"],
                        u.get("role", "user"),
                        u.get("is_early_adopter", 0),
                    ),
                )
                created.append(user_id)
        return created

    def delete_user(self, user_id: str, include_audit: bool = False) -> dict:
        """删除用户及其全部依赖行，返回 ``{"user_id":..., "deleted": {table: n}}``。

        为什么不能直接 ``DELETE FROM users``：
          库内 34 张表以裸外键引用 users(id)，没有任何 ``ON DELETE CASCADE``，
          而连接固定开启 ``PRAGMA foreign_keys=ON``（见 _connect），
          因此父行删除会被外键约束直接拒绝，必须先把子行清干净。

        实现要点：
          1. 以 PRAGMA foreign_key_list 建立依赖图，按**外键反向拓扑序**（子先父后）删除；
          2. 迭代至不动点，以覆盖孙表（如 match_report_items 经由 match_reports 关联）；
          3. 对 NON_FK_USER_TABLES 显式补扫——这些表不参与外键遍历，
             漏掉会在 query_logs / product_events 留下孤儿行，永久污染用量口径。

        ``include_audit=False``（默认）保留 audit_logs 中的审计轨迹。
        """
        with self.get_conn() as conn:
            tabs = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                    " AND name NOT LIKE 'sqlite_%'"
                )
            ]

            pk, fks, children, fk_cols = {}, [], {}, {}
            for t in tabs:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % t)]
                pk[t] = "id" if "id" in cols else "rowid"
                fk_cols[t] = set()
                for fk in conn.execute("PRAGMA foreign_key_list(%s)" % t):
                    parent, child_col = fk[2], fk[3]
                    fks.append((t, child_col, parent))
                    fk_cols[t].add(child_col)
                    if parent != t:
                        children.setdefault(parent, set()).add(t)

            # 外键反向拓扑序：子表排在父表之前
            order, state = [], {}

            def visit(t):
                if state.get(t) in (1, 2):
                    return          # 1=环中，交由不动点迭代兜底
                state[t] = 1
                for ch in children.get(t, ()):
                    visit(ch)
                state[t] = 2
                order.append(t)

            for t in tabs:
                visit(t)

            # 收集待删主键（iterate to fixpoint）
            removed = {t: set() for t in tabs}
            removed["users"] = {user_id}
            for _ in range(30):
                changed = False
                for child, child_col, parent in fks:
                    parent_ids = [v for v in removed.get(parent, ()) if v is not None]
                    if not parent_ids or child == "users":
                        continue
                    found = set()
                    for i in range(0, len(parent_ids), 400):
                        block = parent_ids[i:i + 400]
                        rows = conn.execute(
                            "SELECT %s FROM %s WHERE %s IN (%s)"
                            % (pk[child], child, child_col, ",".join("?" * len(block))),
                            block,
                        ).fetchall()
                        found |= {r[0] for r in rows}
                    found -= removed[child]
                    if found:
                        removed[child] |= found
                        changed = True
                if not changed:
                    break

            deleted = {}

            def _delete(table, column, values):
                n = 0
                for i in range(0, len(values), 400):
                    block = values[i:i + 400]
                    cur = conn.execute(
                        "DELETE FROM %s WHERE %s IN (%s)"
                        % (table, column, ",".join("?" * len(block))),
                        block,
                    )
                    n += cur.rowcount
                return n

            for t in order:
                values = [v for v in removed.get(t, ()) if v is not None]
                if values:
                    n = _delete(t, pk[t], values)
                    if n:
                        deleted[t] = n

            # 补扫无外键表，避免孤儿行
            for table, column, is_audit in NON_FK_USER_TABLES:
                if is_audit and not include_audit:
                    continue
                if table not in tabs:
                    continue
                cur = conn.execute(
                    "DELETE FROM %s WHERE %s = ?" % (table, column), (user_id,)
                )
                if cur.rowcount:
                    deleted[table] = deleted.get(table, 0) + cur.rowcount

            return {"user_id": user_id, "deleted": deleted}

    def rate_query(self, query_id: int, rating: int):
        """Rate a query (1-5)."""
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE query_logs SET rating=? WHERE id=?",
                (rating, query_id),
            )

    def get_last_query_id(self, user_id: str) -> int | None:
        """Get the ID of the user's most recent query."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM query_logs WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return row[0] if row else None

    # ============================================
    # Narrative operations (Jason — Phase 0 feedback)
    # ============================================
    def create_narrative_session(self, user_id: str | None, domain: str) -> str:
        """Create a new narrative session. Returns session_id."""
        session_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO narrative_sessions (id, user_id, domain)
                   VALUES (?, ?, ?)""",
                (session_id, user_id, domain),
            )
        return session_id

    def update_narrative_session(self, session_id: str, status: str,
                                 duration_seconds: float = 0):
        """Mark a session as completed or abandoned."""
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE narrative_sessions
                   SET status=?, duration_seconds=?, ended_at=datetime('now')
                   WHERE id=?""",
                (status, duration_seconds, session_id),
            )

    def log_narrative_event(self, session_id: str, event_type: str,
                            domain: str | None = None,
                            choice: str | None = None,
                            navigator_line: str | None = None,
                            metadata: dict | None = None):
        """Log a narrative event during a session."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO narrative_events
                   (session_id, event_type, domain, choice, navigator_line, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, event_type, domain, choice, navigator_line,
                 json.dumps(metadata or {})),
            )

    def submit_narrative_feedback(self, session_id: str, resonated: bool,
                                  navigator_quote: str | None = None,
                                  would_replay: int | None = None,
                                  shared: bool = False,
                                  share_channel: str | None = None,
                                  open_feedback: str | None = None):
        """Submit convergence-point qualitative feedback."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO narrative_feedback
                   (session_id, resonated, navigator_quote, would_replay,
                    shared, share_channel, open_feedback)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     resonated = excluded.resonated,
                     navigator_quote = excluded.navigator_quote,
                     would_replay = excluded.would_replay,
                     shared = excluded.shared,
                     share_channel = excluded.share_channel,
                     open_feedback = excluded.open_feedback""",
                (session_id, 1 if resonated else 0, navigator_quote, would_replay,
                 1 if shared else 0, share_channel, open_feedback),
            )

    # ============================================================
    # Act 1 state persistence
    # ============================================================

    def save_act1_state(self, session_id: str, state_json: str):
        """Persist Act 1 session state as JSON."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO act1_sessions (session_id, state_json, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(session_id) DO UPDATE SET
                     state_json = excluded.state_json,
                     updated_at = datetime('now')""",
                (session_id, state_json),
            )

    def get_act1_state(self, session_id: str) -> str | None:
        """Retrieve Act 1 session state JSON, or None."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT state_json FROM act1_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return row["state_json"] if row else None

    def get_narrative_stats(self) -> dict:
        """Get aggregated Phase 0 metrics for admin dashboard.

        Returns completion_rate, resonance_rate, share_rate,
        replay_intent_rate, and top navigator quotes.
        """
        with self.get_conn() as conn:
            # Total sessions
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM narrative_sessions"
            ).fetchone()["cnt"]

            # Completed sessions
            completed = conn.execute(
                "SELECT COUNT(*) as cnt FROM narrative_sessions WHERE status='completed'"
            ).fetchone()["cnt"]

            # Feedback stats
            fb_total = conn.execute(
                "SELECT COUNT(*) as cnt FROM narrative_feedback"
            ).fetchone()["cnt"]

            resonated = conn.execute(
                "SELECT COUNT(*) as cnt FROM narrative_feedback WHERE resonated=1"
            ).fetchone()["cnt"]

            shared_cnt = conn.execute(
                "SELECT COUNT(*) as cnt FROM narrative_feedback WHERE shared=1"
            ).fetchone()["cnt"]

            would_replay_yes = conn.execute(
                "SELECT COUNT(*) as cnt FROM narrative_feedback WHERE would_replay=2"
            ).fetchone()["cnt"]

            # Top Navigator quotes (non-empty, deduped, sample)
            quotes = conn.execute(
                """SELECT navigator_quote, COUNT(*) as cnt
                   FROM narrative_feedback
                   WHERE navigator_quote IS NOT NULL AND navigator_quote != ''
                   GROUP BY navigator_quote
                   ORDER BY cnt DESC LIMIT 10"""
            ).fetchall()

            # Per-domain breakdown
            domain_rows = conn.execute(
                """SELECT domain, COUNT(*) as cnt
                   FROM narrative_sessions
                   GROUP BY domain ORDER BY cnt DESC"""
            ).fetchall()

            # Open feedback samples (latest 20)
            open_fb_rows = conn.execute(
                """SELECT nf.open_feedback, ns.domain, nf.created_at
                   FROM narrative_feedback nf
                   JOIN narrative_sessions ns ON nf.session_id = ns.id
                   WHERE nf.open_feedback IS NOT NULL AND nf.open_feedback != ''
                   ORDER BY nf.created_at DESC LIMIT 20"""
            ).fetchall()

        return {
            "total_sessions": total,
            "completed_sessions": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "feedback_count": fb_total,
            "resonance_rate": round(resonated / fb_total * 100, 1) if fb_total > 0 else 0,
            "share_rate": round(shared_cnt / fb_total * 100, 1) if fb_total > 0 else 0,
            "replay_intent_rate": round(would_replay_yes / fb_total * 100, 1) if fb_total > 0 else 0,
            "top_quotes": [{"quote": r["navigator_quote"], "count": r["cnt"]} for r in quotes],
            "domains": [{"domain": r["domain"], "count": r["cnt"]} for r in domain_rows],
            "open_feedback": [{"domain": r["domain"], "text": r["open_feedback"], "at": r["created_at"]} for r in open_fb_rows],
        }

    # ================================================================
    # Value Imprint methods (GDD §3.2)
    # ================================================================

    def get_value_imprints(self, user_id: str) -> dict | None:
        """Get accumulated value imprints for a user."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT survival, freedom, belonging FROM value_imprints WHERE user_id=?",
                (user_id,)
            ).fetchone()
        if row is None:
            return None
        return {"survival": row["survival"], "freedom": row["freedom"], "belonging": row["belonging"]}

    def save_value_imprints(self, user_id: str, imprints: dict):
        """Save/update value imprints for a user."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO value_imprints (user_id, survival, freedom, belonging, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(user_id) DO UPDATE SET
                     survival = excluded.survival,
                     freedom = excluded.freedom,
                     belonging = excluded.belonging,
                     updated_at = excluded.updated_at""",
                (user_id, imprints.get("survival", 0),
                 imprints.get("freedom", 0), imprints.get("belonging", 0)),
            )

    # ================================================================
    # Navigator Memory methods (GDD §3.4)
    # ================================================================

    def record_navigator_memory(self, user_id: str, memory_level: str,
                                content: str, context: str | None = None,
                                domain: str | None = None,
                                importance: float = 1.0,
                                session_id: str | None = None):
        """Persist a Navigator memory entry."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO navigator_memories
                   (user_id, memory_level, content, context, domain, importance, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, memory_level, content, context, domain, importance, session_id),
            )

    def get_navigator_memories(self, user_id: str, memory_level: str | None = None,
                                limit: int = 20) -> list[dict]:
        """Retrieve Navigator memories for a user."""
        if memory_level:
            sql = """SELECT * FROM navigator_memories
                     WHERE user_id=? AND memory_level=?
                     ORDER BY importance DESC, referenced_count ASC
                     LIMIT ?"""
            params = (user_id, memory_level, limit)
        else:
            sql = """SELECT * FROM navigator_memories
                     WHERE user_id=?
                     ORDER BY created_at DESC LIMIT ?"""
            params = (user_id, limit)
        with self.get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def mark_memory_referenced(self, memory_id: int):
        """Increment reference count for a memory."""
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE navigator_memories SET referenced_count = referenced_count + 1 WHERE id=?",
                (memory_id,),
            )

    # ================================================================
    # Emergent Strategy Log (GDD §7.3)
    # ================================================================

    def log_emergent_strategy(self, user_id: str, strategy_type: str):
        """Log an emergent strategy detection."""
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO emergent_strategy_log (user_id, strategy_type) VALUES (?, ?)",
                (user_id, strategy_type),
            )

    def get_emergent_strategies(self, user_id: str) -> list[str]:
        """Get all strategies detected for a user."""
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT strategy_type FROM emergent_strategy_log WHERE user_id=?",
                (user_id,),
            ).fetchall()
        return [r["strategy_type"] for r in rows]

    # ================================================================
    # Domain Visit Log
    # ================================================================

    def log_domain_visit(self, user_id: str, session_id: str, domain: str,
                         previous_domain: str | None = None,
                         interaction_level: str | None = None,
                         echo_triggered: bool = False):
        """Log a domain visit event."""
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO domain_visits
                   (user_id, session_id, domain, previous_domain, interaction_level, echo_triggered)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, session_id, domain, previous_domain, interaction_level,
                 1 if echo_triggered else 0),
            )

    def get_user_domain_history(self, user_id: str, limit: int = 20) -> list[dict]:
        """Get recent domain visit history for a user."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT domain, interaction_level, echo_triggered, entered_at
                   FROM domain_visits WHERE user_id=?
                   ORDER BY entered_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ============================================
    # Product analytics (内测闭环漏斗)
    # ============================================
    def log_product_event(
        self,
        event_name: str,
        user_id: str | None = None,
        session_id: str | None = None,
        platform: str = "unknown",
        share_code: str | None = None,
        source: str = "client",
        success: bool = True,
        properties: dict | None = None,
    ) -> int:
        with self.get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO product_events
                   (event_name, user_id, session_id, platform, share_code, source, success, properties_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_name,
                    user_id,
                    session_id,
                    platform,
                    share_code,
                    source,
                    1 if success else 0,
                    json.dumps(properties or {}, ensure_ascii=False),
                ),
            )
            return cur.lastrowid

    def log_product_events_batch(self, events: list[dict]) -> int:
        count = 0
        for ev in events:
            self.log_product_event(
                event_name=ev["event_name"],
                user_id=ev.get("user_id"),
                session_id=ev.get("session_id"),
                platform=ev.get("platform", "unknown"),
                share_code=ev.get("share_code"),
                source=ev.get("source", "client"),
                success=ev.get("success", True),
                properties=ev.get("properties"),
            )
            count += 1
        return count

    def submit_micro_feedback(
        self,
        context: str,
        score: int,
        optional_text: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        platform: str = "unknown",
        share_code: str | None = None,
    ) -> int:
        with self.get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO micro_feedback
                   (context, score, optional_text, user_id, session_id, platform, share_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (context, score, optional_text, user_id, session_id, platform, share_code),
            )
            return cur.lastrowid

    def get_funnel_stats(self, days: int = 30) -> dict:
        """Aggregate closed-loop funnel counts for internal beta reporting."""
        funnel_events = [
            "quiz_complete",
            "share_code_created",
            "share_link_copied",
            "profile_view_public",
            "hr_register_from_share",
            "candidate_imported",
            "trial_started",
        ]
        since = f"-{int(days)} days"
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT event_name, COUNT(*) as cnt
                   FROM product_events
                   WHERE created_at >= datetime('now', ?)
                   GROUP BY event_name""",
                (since,),
            ).fetchall()
            counts = {r["event_name"]: r["cnt"] for r in rows}

            fb_rows = conn.execute(
                """SELECT context, COUNT(*) as cnt, AVG(score) as avg_score
                   FROM micro_feedback
                   WHERE created_at >= datetime('now', ?)
                   GROUP BY context""",
                (since,),
            ).fetchall()
            feedback = [
                {
                    "context": r["context"],
                    "count": r["cnt"],
                    "avg_score": round(r["avg_score"], 2) if r["avg_score"] is not None else None,
                }
                for r in fb_rows
            ]

        steps = {name: counts.get(name, 0) for name in funnel_events}

        def rate(a: int, b: int) -> float | None:
            if b <= 0:
                return None
            return round(a / b, 4)

        conversion = {
            "share_after_quiz": rate(steps["share_code_created"], steps["quiz_complete"]),
            "view_after_share": rate(steps["profile_view_public"], steps["share_code_created"]),
            "import_after_view": rate(steps["candidate_imported"], steps["profile_view_public"]),
            "trial_after_import": rate(steps["trial_started"], steps["candidate_imported"]),
        }
        return {
            "days": days,
            "steps": steps,
            "conversion": conversion,
            "micro_feedback": feedback,
            "other_events": {
                k: v for k, v in counts.items() if k not in funnel_events
            },
        }

    # ============================================
    # Admin dashboard statistics
    # ============================================

    def get_admin_stats(self) -> dict:
        """Aggregate admin dashboard metrics: users, activity, system overview."""
        with self.get_conn() as conn:
            # ── User counts ──
            total_users = conn.execute(
                "SELECT COUNT(*) as cnt FROM users"
            ).fetchone()["cnt"]

            users_by_tier = {
                r["tier"]: r["cnt"]
                for r in conn.execute(
                    "SELECT tier, COUNT(*) as cnt FROM users GROUP BY tier"
                ).fetchall()
            }

            users_by_role = {
                r["role"]: r["cnt"]
                for r in conn.execute(
                    "SELECT role, COUNT(*) as cnt FROM users GROUP BY role"
                ).fetchall()
            }

            early_adopters = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE is_early_adopter = 1"
            ).fetchone()["cnt"]

            new_users_today = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE created_at >= date('now')"
            ).fetchone()["cnt"]

            new_users_week = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE created_at >= date('now', '-7 days')"
            ).fetchone()["cnt"]

            # ── Activity counts ──
            total_queries = conn.execute(
                "SELECT COUNT(*) as cnt FROM product_events WHERE event_name = 'quiz_complete'"
            ).fetchone()["cnt"]

            def _safe_count(table: str) -> int:
                try:
                    return conn.execute(
                        f"SELECT COUNT(*) as cnt FROM {table}"
                    ).fetchone()["cnt"]
                except Exception:
                    return 0

            total_resumes = _safe_count("resumes")
            total_jobs = _safe_count("jobs")
            total_matches = _safe_count("job_matches")
            total_poems = _safe_count("poems")

            # ── Daily active users (7-day window) ──
            dau_rows = conn.execute(
                """SELECT date(created_at) as day, COUNT(DISTINCT user_id) as cnt
                   FROM product_events
                   WHERE created_at >= date('now', '-7 days')
                   GROUP BY day
                   ORDER BY day DESC"""
            ).fetchall()
            dau_trend = [{"day": r["day"], "count": r["cnt"]} for r in dau_rows]

            # ── Recent registrations ──
            recent_users = conn.execute(
                """SELECT id, email, name, tier, role, created_at
                   FROM users
                   ORDER BY created_at DESC LIMIT 10"""
            ).fetchall()
            recent = [
                {
                    "id": r["id"],
                    "email": r["email"],
                    "name": r["name"],
                    "tier": r["tier"],
                    "role": r["role"],
                    "created_at": r["created_at"],
                }
                for r in recent_users
            ]

            # ── DB size ──
            try:
                page_count = conn.execute("PRAGMA page_count").fetchone()[0]
                page_size = conn.execute("PRAGMA page_size").fetchone()[0]
                db_size_bytes = page_count * page_size
            except Exception:
                db_size_bytes = 0

        return {
            "users": {
                "total": total_users,
                "by_tier": users_by_tier,
                "by_role": users_by_role,
                "early_adopters": early_adopters,
                "new_today": new_users_today,
                "new_this_week": new_users_week,
                "recent": recent,
            },
            "activity": {
                "total_queries": total_queries,
                "total_resumes": total_resumes,
                "total_jobs": total_jobs,
                "total_matches": total_matches,
                "total_poems": total_poems,
                "dau_trend": dau_trend,
            },
            "system": {
                "db_size_bytes": db_size_bytes,
                "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
            },
        }

    # ============================================
    # Quiz sessions (HarmonyOS 答题游戏)
    # ============================================
    def create_quiz_session(self, user_id: str, questions_json: str) -> dict:
        """Create a new quiz session. Returns session dict."""
        import json as _json
        questions = _json.loads(questions_json)
        total = len(questions)
        session_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO quiz_sessions
                   (id, user_id, questions_json, total_questions, status)
                   VALUES (?, ?, ?, ?, 'active')""",
                (session_id, user_id, questions_json, total),
            )
            row = conn.execute(
                "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else {}

    def get_quiz_session(self, session_id: str) -> dict | None:
        """Get a quiz session by ID."""
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def submit_quiz_answer(self, session_id: str, question_id: str,
                           option_ids: list[str], score: int) -> dict | None:
        """Record an answer and advance to next question. Returns updated session."""
        import json as _json
        with self.get_conn() as conn:
            session = conn.execute(
                "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not session:
                return None

            s = dict(session)
            answers = _json.loads(s["answers_json"])
            answers.append({
                "question_id": question_id,
                "option_ids": option_ids,
                "score": score,
            })

            new_index = s["current_index"] + 1
            new_score = s["total_score"] + score
            new_correct = s["correct_count"] + (1 if score > 0 else 0)
            is_completed = new_index >= s["total_questions"]

            status = "completed" if is_completed else "active"
            completed_at = None
            if is_completed:
                from datetime import datetime, timezone, timedelta
                _SHA_TZ = timezone(timedelta(hours=8))
                completed_at = datetime.now(_SHA_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

            conn.execute(
                """UPDATE quiz_sessions SET
                   answers_json = ?, current_index = ?, total_score = ?,
                   correct_count = ?, status = ?, completed_at = ?
                   WHERE id = ?""",
                (
                    _json.dumps(answers, ensure_ascii=False),
                    new_index,
                    new_score,
                    new_correct,
                    status,
                    completed_at,
                    session_id,
                ),
            )

            row = conn.execute(
                "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def complete_quiz_session(self, session_id: str, result_type: str = "",
                              insights_json: str = "[]") -> dict | None:
        """Mark a quiz session as completed and set result metadata."""
        with self.get_conn() as conn:
            from datetime import datetime, timezone, timedelta
            _SHA_TZ = timezone(timedelta(hours=8))
            completed_at = datetime.now(_SHA_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
            conn.execute(
                """UPDATE quiz_sessions SET
                   status = 'completed', result_type = ?, insights_json = ?,
                   completed_at = ?
                   WHERE id = ?""",
                (result_type, insights_json, completed_at, session_id),
            )
            row = conn.execute(
                "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_quiz_history(self, user_id: str, limit: int = 20) -> list[dict]:
        """Get quiz session history for a user."""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT id, total_score, total_questions, correct_count,
                   result_type, status, created_at, completed_at
                   FROM quiz_sessions
                   WHERE user_id = ? AND status = 'completed'
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ============================================
    # Job posts (szbenyx)
    # ============================================
    def count_active_job_posts(self, user_id: str) -> int:
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM job_posts
                   WHERE user_id = ? AND status = 'active'""",
                (user_id,),
            ).fetchone()
        return row["cnt"] if row else 0

    def create_job_post(self, user_id: str, data: dict) -> dict:
        post_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO job_posts
                   (id, user_id, title, company, description, requirements, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    post_id,
                    user_id,
                    data["title"],
                    data.get("company", ""),
                    data.get("description", ""),
                    data.get("requirements", ""),
                    data.get("status", "active"),
                ),
            )
            row = conn.execute("SELECT * FROM job_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row)

    def get_job_posts_by_user(self, user_id: str) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM job_posts WHERE user_id = ?
                   ORDER BY created_at DESC""",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_job_post(self, post_id: str, user_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM job_posts WHERE id = ? AND user_id = ?",
                (post_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def update_job_post(self, post_id: str, user_id: str, data: dict) -> dict | None:
        fields = []
        values = []
        for key in ("title", "company", "description", "requirements", "status"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if not fields:
            return self.get_job_post(post_id, user_id)
        fields.append("updated_at = datetime('now')")
        values.extend([post_id, user_id])
        with self.get_conn() as conn:
            conn.execute(
                f"UPDATE job_posts SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                values,
            )
        return self.get_job_post(post_id, user_id)

    def delete_job_post(self, post_id: str, user_id: str) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM job_posts WHERE id = ? AND user_id = ?",
                (post_id, user_id),
            )
        return cur.rowcount > 0

    def count_enterprise_candidates(self, enterprise_id: str) -> int:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE enterprise_id = ?",
                (enterprise_id,),
            ).fetchone()
        return row["cnt"] if row else 0

    # ============================================
    # Sales inquiries (szbenyx)
    # ============================================
    def create_sales_inquiry(self, data: dict) -> dict:
        inquiry_id = str(uuid.uuid4())
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO sales_inquiries
                   (id, user_id, company_name, contact_name, contact_email,
                    contact_phone, scale, message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    inquiry_id,
                    data.get("user_id"),
                    data["company_name"],
                    data["contact_name"],
                    data["contact_email"],
                    data.get("contact_phone", ""),
                    data.get("scale", ""),
                    data.get("message", ""),
                ),
            )
            row = conn.execute(
                "SELECT * FROM sales_inquiries WHERE id = ?", (inquiry_id,)
            ).fetchone()
        return dict(row)

    # ============================================
    # Orders (szbenyx — 支付订单)
    # ============================================
    def create_order(self, user_id: str, plan_id: str, tier: str,
                     amount: float, currency: str = "CNY",
                     out_trade_no: str | None = None,
                     prepay_id: str = "", qr_code_url: str = "",
                     metadata_json: dict | None = None) -> dict:
        order_id = str(uuid.uuid4())
        if out_trade_no is None:
            out_trade_no = f"LOOMA{_dt_now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO orders
                   (id, user_id, plan_id, tier, amount, currency, out_trade_no,
                    prepay_id, qr_code_url, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, user_id, plan_id, tier, amount, currency,
                    out_trade_no, prepay_id, qr_code_url,
                    json.dumps(metadata_json or {}, ensure_ascii=False),
                ),
            )
            row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row)

    def get_order_by_out_trade_no(self, out_trade_no: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,),
            ).fetchone()
        return dict(row) if row else None

    def get_order_by_id(self, order_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,),
            ).fetchone()
        return dict(row) if row else None

    def mark_order_paid(self, out_trade_no: str, transaction_id: str) -> dict | None:
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE orders SET status = 'paid', transaction_id = ?,
                   paid_at = datetime('now') WHERE out_trade_no = ?""",
                (transaction_id, out_trade_no),
            )
            row = conn.execute(
                "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,),
            ).fetchone()
        return dict(row) if row else None

    def list_user_orders(self, user_id: str, limit: int = 20) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM orders WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ============================================
    # Subscriptions (szbenyx — 用户订阅)
    # ============================================
    def upsert_subscription(self, user_id: str, tier: str, plan_id: str,
                            expires_at: str, auto_renew: bool = False) -> dict:
        from datetime import timedelta
        sub_id = str(uuid.uuid4())
        now = _dt_now().isoformat()
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO subscriptions (id, user_id, tier, plan_id,
                   status, started_at, expires_at, auto_renew)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     tier = excluded.tier,
                     plan_id = excluded.plan_id,
                     status = 'active',
                     expires_at = excluded.expires_at,
                     auto_renew = excluded.auto_renew,
                     updated_at = datetime('now')""",
                (sub_id, user_id, tier, plan_id, now, expires_at, 1 if auto_renew else 0),
            )
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,),
            ).fetchone()
        return dict(row)

    def get_subscription(self, user_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def cancel_subscription(self, user_id: str, at_period_end: bool = False) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute(
                """UPDATE subscriptions SET
                   cancel_at_period_end = ?, updated_at = datetime('now')
                   WHERE user_id = ?""",
                (1 if at_period_end else 0, user_id),
            )
        return cur.rowcount > 0

    def expire_subscription(self, user_id: str) -> bool:
        """Mark subscription as expired and downgrade user to free."""
        with self.get_conn() as conn:
            cur = conn.execute(
                """UPDATE subscriptions SET status = 'expired',
                   updated_at = datetime('now') WHERE user_id = ?""",
                (user_id,),
            )
            if cur.rowcount > 0:
                conn.execute(
                    "UPDATE users SET tier = 'free', updated_at = datetime('now') WHERE id = ?",
                    (user_id,),
                )
        return cur.rowcount > 0

    # ============================================
    # Timeline: career time-series events
    # ============================================
    def insert_timeline_event(
        self,
        user_id: str,
        event_kind: str,
        source_system: str,
        *,
        source_ref: str = "",
        title: str = "",
        summary: str = "",
        payload: dict | None = None,
        signal_quality: str = "observed",
        confidence: float = 0.5,
        weight_role: str = "evidence",
        visibility: str = "private",
        consent_scope: list | None = None,
        occurred_at: str | None = None,
        allow_duplicate: bool = False,
    ) -> dict:
        """Insert or upsert a timeline event. Returns the row as dict.

        Idempotent on (user_id, source_system, source_ref, event_kind) when
        source_ref is non-empty and allow_duplicate is False.
        """
        now = _dt_now().isoformat()
        occurred = occurred_at or now
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        consent_json = json.dumps(consent_scope or [], ensure_ascii=False)
        event_id = f"tle_{uuid.uuid4().hex[:8]}"

        with self.get_conn() as conn:
            existing = None
            if source_ref and not allow_duplicate:
                existing = conn.execute(
                    """SELECT * FROM timeline_events
                       WHERE user_id = ? AND source_system = ?
                         AND source_ref = ? AND event_kind = ?
                         AND status != 'deleted'
                       ORDER BY recorded_at DESC LIMIT 1""",
                    (user_id, source_system, source_ref, event_kind),
                ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE timeline_events SET
                         title = ?, summary = ?, payload_json = ?,
                         signal_quality = ?, confidence = ?, weight_role = ?,
                         visibility = ?, consent_scope = ?,
                         occurred_at = ?, updated_at = datetime('now'),
                         status = 'active'
                       WHERE id = ?""",
                    (
                        title or existing["title"],
                        summary or existing["summary"],
                        payload_json,
                        signal_quality,
                        confidence,
                        weight_role,
                        visibility,
                        consent_json,
                        occurred,
                        existing["id"],
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM timeline_events WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
            else:
                conn.execute(
                    """INSERT INTO timeline_events
                       (id, user_id, event_kind, occurred_at, recorded_at,
                        source_system, source_ref, title, summary, payload_json,
                        signal_quality, confidence, weight_role, visibility,
                        consent_scope, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (
                        event_id, user_id, event_kind, occurred, now,
                        source_system, source_ref, title, summary, payload_json,
                        signal_quality, confidence, weight_role, visibility,
                        consent_json,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM timeline_events WHERE id = ?",
                    (event_id,),
                ).fetchone()
        return dict(row) if row else {}

    def list_timeline_events(
        self,
        user_id: str,
        *,
        event_kind: str | None = None,
        since: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict]:
        """List timeline events newest-first. cursor = occurred_at of last item."""
        limit = max(1, min(int(limit or 50), 100))
        clauses = ["user_id = ?"]
        params: list = [user_id]
        if not include_deleted:
            clauses.append("status != 'deleted'")
        if event_kind:
            clauses.append("event_kind = ?")
            params.append(event_kind)
        if since:
            clauses.append("occurred_at >= ?")
            params.append(since)
        if cursor:
            clauses.append("occurred_at < ?")
            params.append(cursor)
        where = " AND ".join(clauses)
        sql = f"""SELECT * FROM timeline_events
                  WHERE {where}
                  ORDER BY occurred_at DESC, recorded_at DESC
                  LIMIT ?"""
        params.append(limit)
        with self.get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_timeline_event(self, user_id: str, event_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM timeline_events
                   WHERE id = ? AND user_id = ?""",
                (event_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def soft_delete_timeline_event(self, user_id: str, event_id: str) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute(
                """UPDATE timeline_events SET status = 'deleted',
                   updated_at = datetime('now')
                   WHERE id = ? AND user_id = ? AND status != 'deleted'""",
                (event_id, user_id),
            )
        return cur.rowcount > 0

    def supersede_timeline_event(
        self,
        user_id: str,
        event_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        payload: dict | None = None,
    ) -> dict | None:
        """Mark old event superseded and insert a replacement active row."""
        old = self.get_timeline_event(user_id, event_id)
        if not old or old.get("status") == "deleted":
            return None
        old_payload = old.get("payload_json") or "{}"
        if isinstance(old_payload, str):
            try:
                old_payload = json.loads(old_payload)
            except (json.JSONDecodeError, TypeError):
                old_payload = {}
        new_payload = payload if payload is not None else old_payload
        new_row = self.insert_timeline_event(
            user_id=user_id,
            event_kind=old["event_kind"],
            source_system=old["source_system"],
            source_ref=old.get("source_ref") or "",
            title=title if title is not None else old.get("title") or "",
            summary=summary if summary is not None else old.get("summary") or "",
            payload=new_payload if isinstance(new_payload, dict) else {},
            signal_quality=old.get("signal_quality") or "observed",
            confidence=float(old.get("confidence") or 0.5),
            weight_role=old.get("weight_role") or "evidence",
            visibility=old.get("visibility") or "private",
            occurred_at=old.get("occurred_at"),
            allow_duplicate=True,
        )
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE timeline_events SET status = 'superseded',
                   superseded_by = ?, updated_at = datetime('now')
                   WHERE id = ? AND user_id = ?""",
                (new_row.get("id"), event_id, user_id),
            )
        return new_row

    def count_timeline_events(self, user_id: str) -> int:
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS n FROM timeline_events
                   WHERE user_id = ? AND status = 'active'""",
                (user_id,),
            ).fetchone()
        return int(row["n"]) if row else 0
