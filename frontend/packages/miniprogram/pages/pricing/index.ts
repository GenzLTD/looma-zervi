/**
 * Pricing Page — 会员升级页
 *
 * 流程分两路：
 *   Stub 模式 (PAYMENT_STUB_MODE=true) → POST /v1/payment/upgrade 直接升级
 *   生产模式 (PAYMENT_STUB_MODE=false) → POST /v1/payment/wechat/order JSAPI
 *     → wx.requestPayment → 轮询 status → refresh JWT
 */
import { paymentApi, authApi } from '../../utils/api'
import { store } from '../../utils/store'
import { LOOMA_TOKEN_KEY } from '@looma/shared-core'
import type { PaymentPlan, PlansResponse, ProvidersResponse, WechatJsapiParams } from '@looma/shared-core'

const TIER_LABELS: Record<string, string> = {
  free: '免费版',
  supporter: '赞助版',
  pro: '专业版',
  enterprise: '企业版',
}

const TIER_ORDER: Record<string, number> = {
  free: 0,
  supporter: 1,
  pro: 2,
  enterprise: 3,
}

interface PricingCard {
  tier: string
  name: string
  price: string
  features: string[]
  isCurrent: boolean
  isUpgradable: boolean
  buttonText: string
  disabled: boolean
}

Page({
  data: {
    loading: true,
    stubMode: true,
    currentTier: 'free' as string,
    currentTierLabel: '免费版',
    plans: [] as PricingCard[],
    selectedTier: '' as string,
    paying: false,
    polling: false,
    resultModal: false,
    resultTitle: '',
    resultDesc: '',
    resultOk: false,
  },

  onLoad() {
    this.loadPlans()
  },

  onShow() {
    // 每次显示时刷新当前 tier
    this.refreshCurrentTier()
  },

  refreshCurrentTier() {
    const s = store.getAll()
    const user = s.user
    const tier = user?.tier || 'free'
    this.setData({
      currentTier: tier,
      currentTierLabel: TIER_LABELS[tier] || tier,
    })
  },

  async loadPlans() {
    this.setData({ loading: true })
    try {
      // stub_mode 的权威源是 /v1/payment/providers：/plans 是公开面，契约刻意不带该字段
      // （守卫见 backend/tests/test_payment_guard.py）。providers 单独失败不拦定价加载。
      const [data, providers]: [PlansResponse, ProvidersResponse | null] = await Promise.all([
        paymentApi.plans('CN'),
        paymentApi.providers('CN').catch(() => null),
      ])
      // 拿不到 providers 时缺省 false：宁可让用户看到真实支付报错，也不把生产误判成模拟支付
      const stubMode = providers?.stub_mode === true
      const currentTier = this.data.currentTier
      const currentOrder = TIER_ORDER[currentTier] ?? 0

      const cards: PricingCard[] = data.plans.map((plan: PaymentPlan) => {
        const tierOrder = TIER_ORDER[plan.tier] ?? 0
        const isCurrent = plan.tier === currentTier
        const isLower = tierOrder <= currentOrder
        const upgradable = plan.upgradable !== false

        let buttonText = ''
        let disabled = true

        if (isCurrent) {
          buttonText = '当前版本'
          disabled = true
        } else if (isLower) {
          buttonText = '已拥有更高版本'
          disabled = true
        } else if (stubMode && plan.tier !== 'free') {
          buttonText = '立即升级 (内测)'
          disabled = false
        } else if (!stubMode && plan.tier !== 'free') {
          buttonText = `微信支付 ¥${plan.price_monthly}`
          disabled = false
        } else {
          buttonText = '—'
          disabled = true
        }

        return {
          tier: plan.tier,
          name: plan.name,
          price: plan.price_monthly > 0 ? `¥${plan.price_monthly}/月` : '免费',
          features: plan.features || [],
          isCurrent,
          isUpgradable: upgradable,
          buttonText,
          disabled,
        }
      })

      this.setData({
        loading: false,
        stubMode,
        plans: cards,
      })
    } catch (err: any) {
      this.setData({ loading: false })
      wx.showToast({
        title: '加载套餐失败',
        icon: 'none',
      })
      console.error('[Pricing] loadPlans failed:', err)
    }
  },

  /** 点击升级按钮 */
  async handleUpgrade(e: any) {
    const tier = e.currentTarget?.dataset?.tier
    if (!tier || this.data.paying) return

    this.setData({ selectedTier: tier, paying: true })

    try {
      if (this.data.stubMode) {
        await this.doStubUpgrade(tier)
      } else {
        await this.doWechatPay(tier)
      }
    } catch (err: any) {
      this.setData({ paying: false })
      const msg = err?.message || err?.errMsg || '支付失败，请重试'
      wx.showToast({ title: msg, icon: 'none', duration: 3000 })
      console.error('[Pricing] upgrade failed:', err)
    }
  },

  /** Stub 模式：直接调 upgrade API */
  async doStubUpgrade(tier: string) {
    const res: any = await paymentApi.upgrade(tier as 'supporter' | 'pro')

    // 后端 stub upgrade 返回新 token，同步写入双存储
    if (res.access_token) {
      store.set('token', res.access_token)
      wx.setStorageSync(LOOMA_TOKEN_KEY, res.access_token)
    }

    // 刷新用户 profile 以更新 tier
    try {
      const profile = await authApi.profile()
      store.set('user', profile as any)
    } catch {
      // profile refresh 失败不阻塞
    }

    this.setData({ paying: false })
    this.refreshCurrentTier()
    this.loadPlans() // 重新加载，刷新按钮状态

    wx.showToast({ title: '升级成功！', icon: 'success' })
  },

  /** 生产模式：JSAPI 微信支付流程 */
  async doWechatPay(tier: string) {
    // 1. 创建微信支付订单（不传 openid，由后端从 DB 自动填充）
    const order: any = await paymentApi.wechatOrder({
      tier: tier as 'supporter' | 'pro',
      trade_type: 'JSAPI',
    })

    const jsapiParams: WechatJsapiParams | undefined = order?.jsapi_params
    if (!jsapiParams) {
      throw new Error('未获取到支付参数，请重试')
    }

    // 2. 调起微信支付
    await new Promise<void>((resolve, reject) => {
      wx.requestPayment({
        timeStamp: jsapiParams.timeStamp,
        nonceStr: jsapiParams.nonceStr,
        package: jsapiParams.package,
        signType: jsapiParams.signType || 'RSA',
        paySign: jsapiParams.paySign,
        success: () => resolve(),
        fail: (err) => reject(err),
      })
    })

    // 3. 轮询支付状态 + 刷新 JWT
    this.setData({ polling: true })
    await this.pollAndRefresh()

    this.setData({ paying: false, polling: false })
    this.refreshCurrentTier()
    this.loadPlans()

    wx.showToast({ title: '支付成功！', icon: 'success' })
  },

  /** 轮询 /v1/payment/status，确认 tier 已更新后刷新 JWT */
  async pollAndRefresh() {
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 1500))

      try {
        const status: any = await paymentApi.status()
        if (status.tier !== 'free' && status.tier !== this.data.currentTier) {
          // tier 已变化，刷新 JWT
          await this.refreshJWT()
          return
        }
      } catch {
        // 继续轮询
      }
    }
    // 超时也尝试刷新一次
    await this.refreshJWT()
  },

  /** 调用 /v1/auth/refresh 拿新 token */
  async refreshJWT() {
    try {
      const res = await authApi.refresh()
      if (res?.access_token) {
        store.set('token', res.access_token)
        wx.setStorageSync(LOOMA_TOKEN_KEY, res.access_token)
      }
      // 刷新 user profile
      const profile = await authApi.profile()
      store.set('user', profile as any)
    } catch {
      console.warn('[Pricing] JWT refresh failed')
    }
  },

  /** 关闭支付结果弹窗 */
  handleCloseModal() {
    this.setData({ resultModal: false })
  },

  onShareAppMessage() {
    return {
      title: 'PlanetX 会员升级 — 解锁更多职业探索能力！',
      path: '/pages/pricing/index',
    }
  },
})
