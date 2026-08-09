// pages/cards/index.ts — HarmonyOS Service Cards
Page({
  data: {
    // Status cards (2x2 grid)
    statusCards: [
      { id: '1', emoji: '🧑‍💼', value: '28', label: '本周候选人', trendIcon: '↑', trendText: '+12%', trendDirection: 'up' },
      { id: '2', emoji: '📊', value: '146', label: 'AI 问答', trendIcon: '↑', trendText: '+8%', trendDirection: 'up' },
      { id: '3', emoji: '⚡', value: '2.4s', label: '平均响应', trendIcon: '↓', trendText: '-0.3s', trendDirection: 'down' },
      { id: '4', emoji: '✅', value: '94%', label: '准确率', trendIcon: '→', trendText: '稳定', trendDirection: 'flat' },
    ],

    // Action cards (2x2 grid)
    actionCards: [
      { id: 'a1', emoji: '📄', title: '简历解析', desc: '智能提取关键信息', action: 'resume', colorBg: '#EEF2FF' },
      { id: 'a2', emoji: '🧠', title: 'AI 问答', desc: '候选人智能问答', action: 'ask', colorBg: '#F0FDF4' },
      { id: 'a3', emoji: '🔍', title: '职位匹配', desc: '星际精准匹配', action: 'match', colorBg: '#FFF7ED' },
      { id: 'a4', emoji: '📈', title: '数据看板', desc: '实时招聘数据', action: 'dashboard', colorBg: '#F5F3FF' },
    ],

    // Info cards
    infoCards: [
      {
        id: 'i1', tag: '新增', tagColor: '#EEF2FF', tagTextColor: '#0A59F7',
        time: '今天 14:22',
        title: '张明 — 前端工程师',
        detail: '3 年经验 · React/TypeScript · AI 初筛通过 · 待面试',
        footerTitle: '匹配度', footerValue: '92%',
      },
      {
        id: 'i2', tag: '面试中', tagColor: '#FFF7ED', tagTextColor: '#FF7D00',
        time: '今天 10:05',
        title: '李小红 — 全栈开发',
        detail: '5 年经验 · Node.js/Python · 技术面 1/2 已完成',
        footerTitle: '下一轮', footerValue: '明天 15:00',
      },
      {
        id: 'i3', tag: 'Offer', tagColor: '#F0FDF4', tagTextColor: '#00B42A',
        time: '昨天 18:30',
        title: '王磊 — AI 算法工程师',
        detail: '博士 · 计算机视觉方向 · Offer 已发放，等待回复',
        footerTitle: '期望薪酬', footerValue: '面议',
      },
    ],

    // Timeline items
    timelineItems: [
      {
        id: 't1', dotText: '✓', color: '#00B42A',
        title: '简历上传完成', desc: '候选人 张明 简历已解析 12 个关键字段', time: '今天 09:00',
      },
      {
        id: 't2', dotText: '🤖', color: '#0A59F7',
        title: 'AI 初筛通过', desc: '匹配度 92%，符合前端工程师 JD', time: '今天 09:15',
      },
      {
        id: 't3', dotText: '📞', color: '#FF7D00',
        title: 'HR 电话沟通', desc: '确认期望薪资与入职时间', time: '今天 11:30',
      },
      {
        id: 't4', dotText: '📋', color: '#8B5CF6',
        title: '技术面安排', desc: '候选人 + 技术官已确认时间', time: '今天 14:00',
      },
    ],
  },

  onActionTap(e: WechatMiniprogram.TouchEvent) {
    const action = e.currentTarget.dataset.action as string;
    const pageMap: Record<string, string> = {
      resume: '/pages/ask/index',
      ask: '/pages/ask/index',
      match: '/pages/match/index',
      dashboard: '/pages/hub/index',
    };
    const url = pageMap[action] || '/pages/hub/index';
    wx.navigateTo({ url });
  },
});
