import { useEffect } from 'react'
import { usePlanetXStore } from './auth/planetxAuthStore'
import StarBackground from '../brand/components/StarBackground'
import ToastBar from '../brand/components/ToastBar'
import AchievementPopup from '../brand/components/AchievementPopup'
import LoadingScreen from './auth/LoadingScreen'
import AuthScreen from './auth/AuthScreen'
import OnboardingScreen from './onboarding/OnboardingScreen'
import HubScreen from './hub/HubScreen'
import QuizScreen from './quiz/QuizScreen'
import ResultScreen from './result/ResultScreen'
import MatchScreen from './match/MatchScreen'
import TimelineScreen from './timeline/TimelineScreen'
import TrustScreen from './trust/TrustScreen'

/**
 * PlanetX 星际人格测试 — 主入口
 * 迁移自旧 PlanetXHome.tsx
 *
 * 屏幕流转: loading → auth → onboarding → hub ↔ quiz → result → hub
 *                              hub ↔ match / timeline / trust
 */
export default function PlanetXHome() {
  const screen = usePlanetXStore((s) => s.screen)
  const checkSession = usePlanetXStore((s) => s.checkSession)

  useEffect(() => {
    checkSession()
    // 4 秒安全网
    const safety = setTimeout(() => {
      const current = usePlanetXStore.getState().screen
      if (current === 'loading') usePlanetXStore.getState().setScreen('auth')
    }, 4000)
    return () => clearTimeout(safety)
  }, [checkSession])

  const screenComponent = {
    loading: <LoadingScreen />,
    auth: <AuthScreen />,
    onboarding: <OnboardingScreen />,
    hub: <HubScreen />,
    quiz: <QuizScreen />,
    result: <ResultScreen />,
    match: <MatchScreen />,
    timeline: <TimelineScreen />,
    trust: <TrustScreen />,
  }[screen]

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--px-color-bg-page)',
        color: 'var(--px-color-text-bright)',
        display: 'flex',
        justifyContent: 'center',
        overflowX: 'hidden',
        position: 'relative',
      }}
    >
      <StarBackground />
      <ToastBar />
      <AchievementPopup />

      <div
        style={{
          position: 'relative',
          zIndex: 10,
          width: '100%',
          maxWidth: '420px',
          padding: '16px 12px 32px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          animation: 'screenIn 0.4s ease',
        }}
      >
        {/* 全局 CSS 动画注入 */}
        <style>{`
          @keyframes starPulse {
            0%,100% { opacity:0.15; transform:scale(1); }
            50% { opacity:0.8; transform:scale(2.2); }
          }
          @keyframes screenIn {
            from { opacity:0; transform:translateY(16px); }
            to { opacity:1; transform:translateY(0); }
          }
          @keyframes xSpin {
            100% { transform:rotate(360deg); }
          }
          @keyframes fadeIn {
            from { opacity:0; transform:translateY(8px); }
            to { opacity:1; transform:translateY(0); }
          }
        `}</style>

        {screenComponent}
      </div>
    </div>
  )
}
