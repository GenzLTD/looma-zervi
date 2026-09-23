/**
 * Miniprogram runtime config.
 *
 * 环境说明：
 * - 当前固定本地环境：ServBay 反代 http://api.servbay.host
 * - 云上上线时改为：https://api.genz.ltd
 *
 * 本地联调步骤：
 * 1. 确认后端挂在 ServBay 反代域名 api.servbay.host（如后端在 :5200）
 * 2. 微信开发者工具：设置 → 不校验合法域名（本地 http 域名）
 * 3. 构建 npm：pnpm run build:npm
 */

// 本地（ServBay 反代）
export const API_BASE = 'http://api.servbay.host'
// 云上：export const API_BASE = 'https://api.genz.ltd'

export const SAAS_BASE = 'http://localhost:5174'

export const MISSION_XP: Record<string, number> = {
  personality: 50,
  share: 30,
  team: 80,
  match: 40,
}
