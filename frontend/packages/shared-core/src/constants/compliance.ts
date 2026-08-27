import type { ConsentScope, PrimaryConsentScope } from "../types/compliance";

/** Human-readable labels for consent prompts (PIPL 单独同意) */
export const CONSENT_SCOPE_LABELS: Record<ConsentScope, string> = {
  jobseeker_core: "求职核心处理",
  credit_query: "企业风险查询",
  report_share: "匹配报告对外分享",
  resume_upload: "上传简历文件",
  resume_parse: "简历结构化提取",
  job_match: "职位智能匹配",
  report_generate: "生成并保存匹配报告",
  credit_analyze: "征信文本分析",
  profile_share: "分享人格分析结果",
  ask_rag: "AI 知识库问答",
  mbti_analyze: "MBTI 性格测评",
  navigator_memory: "对话记忆持久化",
};

export const CONSENT_SCOPE_DESCRIPTIONS: Record<ConsentScope, string> = {
  jobseeker_core:
    "允许为完成求职匹配而处理您的简历：上传与解析、结构化提取、与职位匹配评分，以及将匹配结果保存为报告供您本人查看。数据会按业务必要范围存储，可随时在本页撤回。",
  credit_query:
    "允许基于企业名称查询工商与风险信息（优先企查查等官方数据源；不可用时可能降级为 AI 参考评估），用于匹配后的企业风险参考，非正式个人征信报告。",
  report_share:
    "允许将匹配报告中您勾选的维度授权给职业成长合伙人查看；未勾选的维度（如企业征信）默认不对外共享。",
  resume_upload:
    "（已并入「求职核心处理」）允许上传并处理简历文件，用于解析与匹配。",
  resume_parse:
    "（已并入「求职核心处理」）允许从简历文本提取结构化字段，用于求职匹配。",
  job_match:
    "（已并入「求职核心处理」）允许使用简历内容与职位进行智能匹配评分。",
  report_generate:
    "（已并入「求职核心处理」）允许将匹配结果持久化为报告，供您后续查看。",
  credit_analyze:
    "（已并入「企业风险查询」）允许分析您粘贴的企业/征信文本并生成摘要。",
  profile_share: "允许生成可分享的公开人格画像链接，供 HR 查看（不含敏感联系方式）。",
  ask_rag: "允许将您的问题发送至 AI 知识库助手，可能结合检索片段生成回答。",
  mbti_analyze: "允许分析您输入的文字以推断性格倾向（娱乐/参考用途）。",
  navigator_memory: "允许 Navigator 在会话间记住您的域选择与关键决策，以延续叙事体验。",
};

/** Product-facing three tiers */
export const CONSENT_PRIMARY_TIERS: PrimaryConsentScope[] = [
  "jobseeker_core",
  "credit_query",
  "report_share",
];

/** Legacy / fine-grained scopes covered by a package */
export const CONSENT_PACKAGES: Partial<Record<ConsentScope, ConsentScope[]>> = {
  jobseeker_core: [
    "resume_upload",
    "resume_parse",
    "job_match",
    "report_generate",
  ],
  credit_query: ["credit_analyze"],
};

/** Map fine-grained API needs → package the user should grant */
export const CONSENT_SCOPE_TO_PACKAGE: Partial<Record<ConsentScope, ConsentScope>> = {
  resume_upload: "jobseeker_core",
  resume_parse: "jobseeker_core",
  job_match: "jobseeker_core",
  report_generate: "jobseeker_core",
  credit_analyze: "credit_query",
};

export function resolveConsentPromptScope(scope: ConsentScope): ConsentScope {
  return CONSENT_SCOPE_TO_PACKAGE[scope] ?? scope;
}
