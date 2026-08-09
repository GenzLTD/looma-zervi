/**
 * SaaS Emoji → Icon 迁移映射表
 *
 * 渐进式替换：旧代码用 emoji 字符串，新代码用 <SaasIcon name="..." />。
 * 提供 mapEmoji() 工具函数方便 Sidebar 等组件迁移。
 */
import type { SaasIconName } from './SaasIcon'

export const EMOJI_TO_ICON: Record<string, SaasIconName> = {
  '◉': 'dashboard',
  '✦': 'candidates',
  '◈': 'jobs',
  '◎': 'query',
  '⬡': 'resume',
  '◆': 'match',
  '◧': 'report',
  '⚙': 'settings',
  '◻': 'pipeline',
  '◫': 'compare',
  '▣': 'radar',
  '🧠': 'robot',
  '📄': 'resume',
  '📊': 'chart',
  '⏳': 'timer',
  '📥': 'download',
  '📤': 'upload',
  '🔍': 'query',
  '✓': 'check',
  '✗': 'cross',
  '⚠': 'warning',
  'ℹ': 'info',
  '👥': 'candidates',
  '📋': 'resume',
  '🏆': 'match',
  '📈': 'chart',
}

export function mapEmoji(emoji: string): SaasIconName | undefined {
  return EMOJI_TO_ICON[emoji]
}
