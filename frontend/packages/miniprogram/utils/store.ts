/**
 * Global store for miniprogram.
 * Centralized state management using app.globalData + event bus.
 * Pages subscribe to events and read from store.
 */

import { eventBus } from './event-bus'
import { 
  User, 
  Identity, 
  PersonalityType as PlanetXPersonalityType, 
  MissionId, 
  Fleet,
  GameProfile
} from '../types/index'
import { hydratePersonality } from '../constants/quiz'

const STORAGE_KEY = 'planetx_store_v1'

// 需要持久化的字段（避免 UI 瞬时状态如 achievement 被保存）
const PERSISTED_KEYS: (keyof StoreState)[] = [
  'token',
  'user',
  'identity',
  'personalityType',
  'personalityDetail',
  'level',
  'xp',
  'xpToNext',
  'missionsCompleted',
  'fleet',
  'teamSize',
  'fleetMembers',
  'spreadCount',
  'quizStep',
  'quizTraitCounts',
]

interface StoreState {
  // Auth
  token: string | null
  user: User | null

  // Game
  identity: Identity | undefined
  personalityType: PlanetXPersonalityType | undefined
  level: number
  xp: number
  xpToNext: number
  missionsCompleted: MissionId[]

  // Fleet
  fleet: Fleet | null
  teamSize: number
  fleetMembers: string[]
  spreadCount: number

  // Quiz
  quizStep: number
  quizTraitCounts: Partial<Record<string, number>>

  // UI
  achievement: { title: string; desc: string } | null
  personalityDetail?: string
}

const state: StoreState = {
  token: null,
  user: null,
  identity: undefined,
  personalityType: undefined,
  level: 1,
  xp: 0,
  xpToNext: 100,
  missionsCompleted: [],
  fleet: null,
  teamSize: 0,
  fleetMembers: [],
  spreadCount: 0,
  quizStep: 0,
  quizTraitCounts: {},
  achievement: null,
  personalityDetail: undefined,
}

/** Hydrate in-memory state from local storage on module load */
function hydrateFromStorage() {
  try {
    const raw = wx.getStorageSync(STORAGE_KEY)
    if (!raw) return
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    for (const key of PERSISTED_KEYS) {
      if (parsed[key] !== undefined) {
        ;(state as any)[key] = parsed[key]
      }
    }
    // 重建 personalityType 对象（存储的是普通对象，类型系统需要 any）
    const restored = state.personalityType
    if (restored && typeof restored === 'object') {
      state.personalityType = restored as any
    }
  } catch (e) {
    console.warn('[Store] hydrate failed:', e)
  }
}

/** Persist current state to local storage */
function persistToStorage() {
  try {
    const toPersist: Partial<StoreState> = {}
    for (const key of PERSISTED_KEYS) {
      ;(toPersist as any)[key] = state[key]
    }
    wx.setStorageSync(STORAGE_KEY, toPersist)
  } catch (e) {
    console.warn('[Store] persist failed:', e)
  }
}

// 启动时从本地恢复
hydrateFromStorage()

export const store = {
  get: <K extends keyof StoreState>(key: K): StoreState[K] => state[key],

  getAll: (): StoreState => state,

  set: <K extends keyof StoreState>(key: K, value: StoreState[K]) => {
    state[key] = value
    persistToStorage()
  },

  /** Update game profile from backend response */
  applyGameProfile(data: any) {
    // 兼容后端返回的字段命名（可能是 snake_case）
    const identity = data.identity !== undefined ? data.identity : undefined
    const level = data.level !== undefined ? data.level : undefined
    const xp = data.xp !== undefined ? data.xp : undefined
    const personality_type = data.personality_type !== undefined ? data.personality_type : data.personalityType
    const missions_completed = data.missions_completed !== undefined ? data.missions_completed : data.missionsCompleted
    const fleet = data.fleet !== undefined ? data.fleet : undefined
    const team_size = data.team_size !== undefined ? data.team_size : data.teamSize
    const fleet_members = data.fleet_members !== undefined ? data.fleet_members : data.fleetMembers
    const spread_count = data.spread_count !== undefined ? data.spread_count : data.spreadCount
    const personality_detail = data.personality_detail !== undefined ? data.personality_detail : undefined

    if (identity !== undefined) state.identity = identity
    if (level !== undefined) state.level = level
    if (xp !== undefined) state.xp = xp
    // 注意：shared-core 的 GameProfile 中没有 xp_to_next 字段
    // 保持现有的 xpToNext 逻辑不变

    if (personality_detail !== undefined) {
      state.personalityDetail = personality_detail
    }

    const personality = hydratePersonality(
      typeof personality_type === 'string' ? personality_type : undefined,
      personality_detail,
    )
    if (personality) {
      state.personalityType = personality as any
    } else if (personality_type === '' || personality_type === null) {
      state.personalityType = undefined
    }

    if (missions_completed !== undefined) {
      // 处理 missions_completed 可能是数字或数组的情况
      if (Array.isArray(missions_completed)) {
        state.missionsCompleted = missions_completed as MissionId[]
      } else if (typeof missions_completed === 'number') {
        // 如果是数字，转换为空数组（因为小程序需要数组）
        state.missionsCompleted = []
      }
    }
    if (fleet !== undefined) state.fleet = fleet
    if (team_size !== undefined) state.teamSize = team_size
    if (fleet_members !== undefined) state.fleetMembers = fleet_members
    if (spread_count !== undefined) state.spreadCount = Number(spread_count) || 0
    persistToStorage()
    eventBus.emit('profile:loaded', state)
  },

  /** Add XP and handle level up */
  addXP(amount: number) {
    state.xp += amount
    let leveledUp = false
    while (state.xp >= state.xpToNext) {
      state.xp -= state.xpToNext
      state.level++
      state.xpToNext = Math.floor(state.xpToNext * 1.5)
      leveledUp = true
    }
    if (leveledUp) {
      store.setAchievement({
        title: '⬆️ 升级！',
        desc: `你已晋升为 Lv.${state.level}`,
      })
    }
    persistToStorage()
    eventBus.emit('xp:added', { xp: state.xp, level: state.level })
  },

  /** Complete a mission */
  completeMission(id: MissionId) {
    if (state.missionsCompleted.includes(id)) return
    state.missionsCompleted = [...state.missionsCompleted, id]
    persistToStorage()
  },

  /** Set identity and sync to backend */
  async setIdentity(identity: Identity) {
    state.identity = identity
    persistToStorage()

    // 同步到后端（best-effort）
    const token = state.token
    if (token) {
      try {
        // 动态 import 避免循环依赖
        const { gameApi } = await import('./api')
        await gameApi.syncProfile({ personality_type: '', identity })
      } catch {
        console.warn('[Store] identity sync failed (non-critical)')
      }
    }
  },

  /** Set achievement popup */
  setAchievement(a: { title: string; desc: string } | null) {
    state.achievement = a
    eventBus.emit('achievement', a)
    if (a) {
      setTimeout(() => {
        state.achievement = null
        eventBus.emit('achievement', null)
      }, 2500)
    }
  },

  /** Reset all state (logout) */
  reset() {
    state.token = null
    state.user = null
    state.identity = undefined
    state.personalityType = undefined
    state.level = 1
    state.xp = 0
    state.xpToNext = 100
    state.missionsCompleted = []
    state.fleet = null
    state.teamSize = 0
    state.fleetMembers = []
    state.spreadCount = 0
    state.quizStep = 0
    state.quizTraitCounts = {}
    state.achievement = null
    try {
      wx.removeStorageSync(STORAGE_KEY)
    } catch (e) {
      console.warn('[Store] removeStorage failed:', e)
    }
  },
}
