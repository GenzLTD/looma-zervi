/**
 * 上架前隐私告知常量（PIPL / 2026-08 通报第 1、2 类）。
 * 完整政策正文见各端 /legal/privacy 页。
 */
export const LEGAL = {
  privacyPath: "/legal/privacy",
  operatorName: "深伯乐科技",
  operatorContact: "privacy@szbolent.com.cn",
  dataRetention:
    "账号存续期间处理；注销后对邮箱、openid、姓名等予以匿名化，审计日志按法规留存不少于6个月。",
  minAge: 14,
  privacyAcceptedKey: "looma_privacy_accepted",
  ageConfirmedKey: "looma_age_confirmed",
} as const;

export const LEGAL_PRIVACY_SUMMARY = [
  `运营主体：${LEGAL.operatorName}`,
  `联系方式：${LEGAL.operatorContact}`,
  `保存期限：${LEGAL.dataRetention}`,
  "处理目的：账号、人格测评、求职匹配、六度关系链、AI 问答。",
  "第三方：微信登录/支付、DeepSeek（境内大模型）；若启用 OpenAI 将另行单独告知。",
].join("\n");
