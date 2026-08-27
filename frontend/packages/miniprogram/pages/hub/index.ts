/**
 * Hub Page - TabBar home (index 0)
 * XP bar + mission list + fleet panel + profile stats
 */
import { eventBus } from '../../utils/event-bus'
import { store } from '../../utils/store'
import { gameApi } from '../../utils/api'
import { IDENTITY_LABELS, hydratePersonality } from '../../types/index'
import type { MissionId, Identity } from '../../types/index'

Page({
  data: {
    // Game state
    level: 1,
    xp: 0,
    xpToNext: 100,
    identity: '' as string,
    identityLabel: '',
    personalityName: '',
    personalityEmoji: '',
    personalityTagline: '',
    missionsCompleted: [] as string[],
    teamSize: 0,
    spreadCount: 0,
    fleet: null as any,
    fleetMembers: [] as string[],

    // UI
    activeTab: 'missions',
    showFleetModal: false,
    fleetJoinCode: '',
    fleetJoining: false,
    fleetCreating: false,
    missions: [
      { id: 'personality', icon: '🔮', name: '星际人格测试', reward: '+50 XP · 解锁专属星球身份', xp: 50, requires: '' },
      { id: 'team', icon: '🤝', name: '组建3人舰队', reward: '+80 XP · 解锁隐藏星图', xp: 80, requires: 'personality' },
      { id: 'match', icon: '🎯', name: '首次星际匹配', reward: '+40 XP · 获得匹配星图', xp: 40, requires: 'team' },
      { id: 'share', icon: '📡', name: '发送星际信号', reward: '+30 XP · 邀请好友获得额外能量', xp: 30, requires: 'personality' },
    ],
  },

  _profileHandler: null as any,
  _profileLoaded: false,

  onLoad() {
    console.log('[Hub] onLoad')
    this._profileHandler = () => this.refreshFromStore()
    eventBus.on('profile:loaded', this._profileHandler)
  },

  onShow() {
    console.log('[Hub] onShow')

    // Update tab bar selected state (custom tab bar)
    const tabBar = (this as any).getTabBar?.()
    if (tabBar) tabBar.setData({ selected: 0 })

    this.refreshFromStore()

    // Lazy-load profile from backend (deferred from app.onLaunch for performance)
    if (!this._profileLoaded) {
      this._profileLoaded = true
      const app = getApp() as any
      if (app.loadProfile) {
        console.log('[Hub] Triggering loadProfile from hub page')
        app.loadProfile()
      }
    }

    // Also refresh fleet data if user is logged in
    this.loadFleetData()
  },

  onUnload() {
    if (this._profileHandler) eventBus.off('profile:loaded', this._profileHandler)
  },

  async loadFleetData() {
    const token = store.get('token')
    if (!token) return
    try {
      const data: any = await gameApi.getMyFleet()
      if (data?.fleet) {
        store.set('fleet', data.fleet)
        store.set('teamSize', data.team_size ?? data.member_count ?? 0)
        store.set('fleetMembers', data.fleet_members ?? [])
        this.refreshFromStore()

        // 检查是否达成3人舰队任务
        const teamSize = store.get('teamSize')
        const completed = store.get('missionsCompleted')
        if (teamSize >= 3 && !completed.includes('team')) {
          this.completeFleetMission()
        }
      }
    } catch {
      // fleet data is optional
    }
  },

  async completeFleetMission() {
    try {
      const data: any = await gameApi.completeMission('team', 80)
      store.completeMission('team')
      // XP 仅从后端 total_xp 写入，无本地 addXP，避免双计
      if (data?.total_xp != null) {
        store.applyGameProfile({ xp: data.total_xp, level: data.level, missions_completed: store.get('missionsCompleted') })
      }
      store.setAchievement({ title: '🤝 舰队集结完毕！', desc: '3人成团 · 隐藏星图已解锁' })
      this.refreshFromStore()
    } catch (err: any) {
      // 409 = 已回写，仅更新本地状态
      const status = err?.status || err?.statusCode
      if (status === 409) {
        store.completeMission('team')
        this.refreshFromStore()
        return
      }
      console.warn('[Hub] completeFleetMission failed:', err?.message || err)
    }
  },

  refreshFromStore() {
    const s = store.getAll()
    // 使用 hydratePersonality 获取完整的 PersonalityType 对象
    const personalityObj = hydratePersonality(s.personalityType, s.personalityDetail)

    this.setData({
      level: s.level,
      xp: s.xp,
      xpToNext: s.xpToNext,
      identity: s.identity || '',
      identityLabel: s.identity ? IDENTITY_LABELS[s.identity] : '',
      personalityName: personalityObj?.name || '',
      personalityEmoji: personalityObj?.emoji || '',
      personalityTagline: personalityObj?.tagline || '',
      missionsCompleted: s.missionsCompleted,
      teamSize: s.teamSize,
      spreadCount: s.spreadCount ?? 0,
      fleet: s.fleet,
      fleetMembers: s.fleetMembers,
    })
  },

  switchTab(e: any) {
    this.setData({ activeTab: e.currentTarget.dataset.tab })
  },

  onMissionTap(e: any) {
    const id = e.currentTarget.dataset.id as MissionId
    const mission = this.data.missions.find((m) => m.id === id)
    if (!mission) return

    // Check if locked
    if (mission.requires && !this.data.missionsCompleted.includes(mission.requires)) {
      wx.showToast({ title: '需先完成前置任务', icon: 'none' })
      return
    }

    // Check if already done
    if (this.data.missionsCompleted.includes(id)) {
      wx.showToast({ title: '已完成', icon: 'none' })
      return
    }

    // Route based on mission type
    if (id === 'personality') {
      wx.navigateTo({ url: '/pages/quiz/index' })
    } else if (id === 'team') {
      this.onTeamMissionTap()
    } else if (id === 'match') {
      wx.navigateTo({ url: '/pages/match/index' })
    } else if (id === 'share') {
      if (!this.data.personalityName && !this.data.missionsCompleted.includes('personality')) {
        wx.showToast({ title: '请先完成人格测试', icon: 'none' })
        return
      }
      wx.navigateTo({ url: '/pages/result/index' })
    }
  },

  goToTrust() {
    wx.navigateTo({ url: '/pages/trust/index' })
  },

  // ── Fleet operations ──

  onTeamMissionTap() {
    // 如果已有舰队，展示舰队详情
    if (this.data.fleet) {
      this.setData({ activeTab: 'team' })
      return
    }
    // 否则弹窗让用户选择创建还是加入
    wx.showActionSheet({
      itemList: ['创建舰队', '加入舰队'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.onCreateFleetTap()
        } else {
          this.showJoinFleetModal()
        }
      },
    })
  },

  async onCreateFleetTap() {
    if (this.data.fleetCreating) return
    this.setData({ fleetCreating: true })
    try {
      const data: any = await gameApi.createFleet('星际舰队')
      store.set('fleet', { id: data.id, name: data.name, invite_code: data.invite_code, captain_id: data.captain_id })
      store.set('teamSize', data.team_size ?? 1)
      store.set('fleetMembers', [])
      this.refreshFromStore()
      wx.showToast({ title: '舰队创建成功！', icon: 'success' })
    } catch (err: any) {
      const msg = err?.message || err?.error || '创建失败'
      wx.showToast({ title: msg, icon: 'none' })
    } finally {
      this.setData({ fleetCreating: false })
    }
  },

  showJoinFleetModal() {
    this.setData({ showFleetModal: true, fleetJoinCode: '' })
  },

  hideJoinFleetModal() {
    this.setData({ showFleetModal: false, fleetJoinCode: '' })
  },

  onJoinCodeInput(e: any) {
    this.setData({ fleetJoinCode: e.detail.value })
  },

  async onJoinFleetConfirm() {
    const code = this.data.fleetJoinCode.trim()
    if (!code) {
      wx.showToast({ title: '请输入邀请码', icon: 'none' })
      return
    }
    if (this.data.fleetJoining) return
    this.setData({ fleetJoining: true })
    try {
      await gameApi.joinFleet(code)
      this.hideJoinFleetModal()
      wx.showToast({ title: '加入舰队成功！', icon: 'success' })
      // 刷新舰队数据
      await this.loadFleetData()
    } catch (err: any) {
      const msg = err?.message || err?.error || '加入失败'
      wx.showToast({ title: msg, icon: 'none' })
    } finally {
      this.setData({ fleetJoining: false })
    }
  },

  onCopyInviteCode() {
    const code = this.data.fleet?.invite_code || ''
    if (!code) return
    wx.setClipboardData({
      data: code,
      success: () => wx.showToast({ title: '邀请码已复制！', icon: 'success' }),
    })
  },
})
