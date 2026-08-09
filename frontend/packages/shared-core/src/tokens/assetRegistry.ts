/**
 * Brand Asset Registry
 * ===================
 * 集中管理所有品牌资源的逻辑名称 → 文件路径映射。
 *
 * 设计师交付优化版资产后，只需：
 *   1. 将文件放入对应 public/brand/ 目录
 *   2. 更新此文件中对应的 path
 *
 * 当前 status：
 *   - ✓ 路径已预留，资产待替换
 *   - 组件（BrandIllustration / BrandAvatar）已实现，可立即渲染
 */

export interface AssetEntry {
  /** 逻辑名称，用于代码引用 */
  name: string
  /** public/ 下的路径，如 "/brand/illustrations/hero.png" */
  path: string
  /** 资产类型 */
  type: 'illustration' | 'avatar' | 'wallpaper' | 'icon'
  /** 资产状态 */
  status: 'ready' | 'pending' | 'placeholder'
  /** 描述 */
  description: string
}

// ================================================================
// PlanetX 资产清单
// ================================================================
export const PLANETX_ASSETS: AssetEntry[] = [
  // 3D 插画（Figma 已有 10 张 glass_*，待设计师导出 Web 优化版）
  {
    name: 'px-hero-galaxy',
    path: '/brand/illustrations/planetx/galaxy_hero.png',
    type: 'illustration',
    status: 'pending',
    description: 'HubScreen Hero 背景 — 深空星系插画 (Figma: galaxy_purple.png)',
  },
  {
    name: 'px-fleet-empty',
    path: '/brand/illustrations/planetx/fleet_empty.png',
    type: 'illustration',
    status: 'pending',
    description: '舰队空状态 — 邀请队友插画 (Figma: glass_network_hub.png)',
  },
  {
    name: 'px-mission',
    path: '/brand/illustrations/planetx/mission.png',
    type: 'illustration',
    status: 'pending',
    description: '任务/探索 — 3D 插画 (Figma: glass_steps.png)',
  },
  {
    name: 'px-achievement',
    path: '/brand/illustrations/planetx/achievement.png',
    type: 'illustration',
    status: 'pending',
    description: '成就 — 奖杯插画 (Figma: glass_stacked_cubes.png)',
  },
  {
    name: 'px-matching',
    path: '/brand/illustrations/planetx/matching.png',
    type: 'illustration',
    status: 'pending',
    description: '星际匹配 — 连接插画 (Figma: glass_interlocking_rings.png)',
  },
  // 头像（Figma 已有 6 张 avatar_*，保留原始 4000px 版本）
  {
    name: 'avatar-man-beard-purple',
    path: '/brand/avatars/planetx/man_beard_purple.png',
    type: 'avatar',
    status: 'pending',
    description: '男性用户头像 — 紫色调 (Figma: avatar_man_beard_purple.png)',
  },
  {
    name: 'avatar-woman-redhair-purple',
    path: '/brand/avatars/planetx/woman_redhair_purple.png',
    type: 'avatar',
    status: 'pending',
    description: '女性用户头像 — 紫色调 (Figma: avatar_woman_redhair_purple.png)',
  },
  // 壁纸
  {
    name: 'px-wallpaper-galaxy',
    path: '/brand/wallpapers/planetx/galaxy_purple.png',
    type: 'wallpaper',
    status: 'pending',
    description: 'PlanetX 全屏背景壁纸 (Figma: galaxy_purple.png)',
  },
]

// ================================================================
// TSpace 资产清单
// 详细交付规格见: docs/design-hi-fi/DESIGNER_HANDOFF_TSPACE.md
// ================================================================
export const TSPACE_ASSETS: AssetEntry[] = [
  // --- P0: 必须出图 ---
  {
    name: 'tsp-hero-banner',
    path: '/brand/illustrations/tsaas/hero_banner.png',
    type: 'illustration',
    status: 'pending',
    description: 'Dashboard 顶部横幅 — 1440×300 品牌插画',
  },
  {
    name: 'tsp-empty-candidates',
    path: '/brand/illustrations/tsaas/empty_candidates.png',
    type: 'illustration',
    status: 'pending',
    description: '候选人空列表 — 400×400 扁平办公插画',
  },
  {
    name: 'tsp-empty-results',
    path: '/brand/illustrations/tsaas/empty_results.png',
    type: 'illustration',
    status: 'pending',
    description: '通用无搜索/无匹配 — 400×400 扁平办公插画',
  },
  // --- P0+: 品牌识别 ---
  {
    name: 'tsp-logo',
    path: '/brand/illustrations/tsaas/logo.svg',
    type: 'icon',
    status: 'pending',
    description: 'TSpace 正式 Logo SVG（水平版+方版），替换 BrandMark 几何 T',
  },
  {
    name: 'tsp-favicon',
    path: '/brand/illustrations/tsaas/favicon.ico',
    type: 'icon',
    status: 'pending',
    description: '浏览器标签图标 32×32/16×16',
  },
  {
    name: 'tsp-apple-touch-icon',
    path: '/brand/illustrations/tsaas/apple-touch-icon.png',
    type: 'icon',
    status: 'pending',
    description: 'iOS 主屏幕 / PWA 图标 180×180',
  },
  {
    name: 'tsp-og-share',
    path: '/brand/illustrations/tsaas/og-share.png',
    type: 'illustration',
    status: 'pending',
    description: '海外落地页 OG 分享图 1200×630 (上线前补即可)',
  },
  // --- P1: 替换 emoji / 补充插画 ---
  {
    name: 'tsp-error-state',
    path: '/brand/illustrations/tsaas/error_state.png',
    type: 'illustration',
    status: 'pending',
    description: '通用错误态 — 400×400（替换 ⚠️ emoji）',
  },
  {
    name: 'tsp-empty-trust',
    path: '/brand/illustrations/tsaas/empty_trust.png',
    type: 'illustration',
    status: 'pending',
    description: '信任档案空状态 — 400×400（可复用 empty_results 同系）',
  },
  {
    name: 'tsp-empty-jobs',
    path: '/brand/illustrations/tsaas/empty_jobs.png',
    type: 'illustration',
    status: 'pending',
    description: '职位匹配无结果 — 400×400（可复用 empty_results）',
  },
  {
    name: 'tsp-personality-icons',
    path: '/brand/illustrations/tsaas/personality/',
    type: 'illustration',
    status: 'pending',
    description: '人格类型视觉套 8–12 型 — 200×200/套（替换候选人 🪐 emoji）',
  },
  {
    name: 'tsp-report-icons',
    path: '/brand/illustrations/tsaas/report_types/',
    type: 'icon',
    status: 'pending',
    description: '报告中心类型图标 — 48×48/项（替换 📊📈📋📄）',
  },
  {
    name: 'tsp-poetry-empty',
    path: '/brand/illustrations/tsaas/empty_poetry.png',
    type: 'illustration',
    status: 'pending',
    description: '诗意空间空状态 — 400×400（大陆专属，海外可后置）',
  },
]

// ================================================================
// 工具函数
// ================================================================
export function getAssetPath(name: string): string | undefined {
  return [...PLANETX_ASSETS, ...TSPACE_ASSETS].find((a) => a.name === name)?.path
}

export function getAssetsByType(type: AssetEntry['type']): AssetEntry[] {
  return [...PLANETX_ASSETS, ...TSPACE_ASSETS].filter((a) => a.type === type)
}

export function getPendingAssets(): AssetEntry[] {
  return [...PLANETX_ASSETS, ...TSPACE_ASSETS].filter((a) => a.status === 'pending')
}
