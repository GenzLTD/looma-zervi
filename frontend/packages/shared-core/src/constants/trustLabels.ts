/**
 * 信任档案翻译表 — 单一真源（shared-core）
 *
 * RULE: 所有终端（Web / 小程序 / PlanetX）均从此 import，
 * 不允许各自硬编码副本。翻译迭代由产品/HR 共建此映射表。
 *
 * 禁止画 social 信用分，信任呈现走 attestation 卡片。
 */

/** 声明类型 → 中文标签 */
export const CLAIM_LABEL: Record<string, string> = {
  identity: "身份声明",
  collaboration: "协作声明",
  communication: "沟通声明",
  influence: "影响声明",
};

/** 验证状态 → 中文标签 */
export const STATUS_LABEL: Record<string, string> = {
  verified: "已验证",
  verified_by_authority: "权威验证",
  weak: "弱证据",
  unverified: "待沉淀",
  disputed: "有争议",
};

/** 验证状态 → 色标（hex） */
export const STATUS_COLOR: Record<string, string> = {
  verified: "#4ade80",
  verified_by_authority: "#22d3ee",
  weak: "#fbbf24",
  unverified: "#94a3b8",
  disputed: "#ef4444",
};

/** 证据类型 → 中文标签 */
export const EVIDENCE_LABEL: Record<string, string> = {
  quiz: "知识测验",
  fleet_consensus: "舰队共识",
  dialogue_analysis: "对话分析",
  share_signal: "信号传播",
  credential: "凭证验证",
  match_scan: "匹配扫描",
  resume: "简历解析",
  fleet: "舰队成就",
};

// ============================================================
// 兜底默认值 — 映射表查不到时的 fallback，禁止各自硬编码
// ============================================================

/** evidence_type 查无映射时的默认标签 */
export const EVIDENCE_FALLBACK = "行为凭证";

/** claim_type 查无映射时的默认标签 */
export const CLAIM_FALLBACK = "信任声明";

/** status 查无映射时的默认标签（兜底按英文原值显示） */
export const STATUS_FALLBACK_KEY = true; // truthy → 显示原始 key 而非静默 fallback
