/**
 * Looma Design Token — 统一出口
 * ==================================
 * 使用方式（各品牌直接 import 对应文件）：
 *   import '@looma/shared-core/tokens/base.css'
 *   import '@looma/shared-core/tokens/planetx.css'
 *
 * 三层架构：
 *   base.css      共享基础（间距/圆角/字体/动效/Z-index）
 *   planetx.css   PlanetX 品牌（深空游戏主题）
 *   saas.css      TSpace 品牌（企业 SaaS 主题）
 *   harmony.css   鸿蒙元服务（HM Design System）
 *
 * Token 命名规范：
 *   基础  → --lo-*      (所有品牌共用)
 *   PlanetX → --px-*    (品牌特定)
 *   TSpace  → --tsp-*   (品牌特定)
 *   鸿蒙    → --hm-*     (品牌特定)
 *
 * Figma → Code 映射规则：
 *   colors/primary    → --{prefix}-brand-primary
 *   colors/surface    → --{prefix}-color-surface-*
 *   colors/text       → --{prefix}-color-text-*
 *   colors/border     → --{prefix}-color-border-*
 *   effects/shadows   → --{prefix}-shadow-*
 *   typography/font   → --{prefix}-font-*
 *
 * 版本：v2.0 — 统一自 Figma 2026-08-08 第一期风格设计
 */

export const TOKENS_VERSION = '2.0.0'
export const TOKENS_FIGMA_SOURCE = '20260808_第一期风格设计_figma'
