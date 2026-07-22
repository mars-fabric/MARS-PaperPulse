'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { FileText, Sparkles, Upload, PanelRightClose, PanelRightOpen, ArrowRight, Activity, BadgeCheck, Layers3 } from 'lucide-react'
import TopBar from '@/components/layout/TopBar'
import SessionSidebar from '@/components/sessions/SessionSidebar'
import type { SessionItem } from '@/components/sessions/SessionSidebar'
import DeepresearchResearchTask from '@/components/tasks/DeepresearchResearchTask'
import LoginModal from '@/components/auth/LoginModal'
import SignupModal from '@/components/auth/SignupModal'
import PendingApproval from '@/components/auth/PendingApproval'
import UserMenu from '@/components/layout/UserMenu'
import SimpleDashboardLanding from '@/components/dashboard/SimpleDashboardLanding'
import { useAuth } from '@/contexts/AuthContext'
import { useResizableSidebar } from '@/hooks/useResizableSidebar'
import { apiCall } from '@/lib/api'

export default function Home() {
  return <AuthGate />
}

// ─── Auth Gate — renders login/signup/pending screens before the main app ───

function AuthGate() {
  const { user, isLoading } = useAuth()
  const [authView, setAuthView] = useState<'none' | 'login' | 'signup'>('none')
  const [signupNotice, setSignupNotice] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-950">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
      </div>
    )
  }

  // Show pending approval screen after signup
  if (user?.status === 'pending') {
    return <PendingApproval />
  }

  // Show login/signup if not authenticated
  if (!user) {
    return (
      <div className="h-full relative">
        <PublicAuthLanding
          onSignIn={() => {
            setSignupNotice(null)
            setAuthView('login')
          }}
          onSignUp={() => {
            setSignupNotice(null)
            setAuthView('signup')
          }}
          signupNotice={signupNotice}
        />

        <LoginModal
          open={authView === 'login'}
          onClose={() => setAuthView('none')}
          onSwitchToSignup={() => setAuthView('signup')}
        />

        <SignupModal
          open={authView === 'signup'}
          onClose={() => setAuthView('none')}
          onSignedUp={() => {
            setAuthView('login')
            setSignupNotice('Account created successfully. Please sign in after admin approval.')
          }}
          onSwitchToLogin={() => setAuthView('login')}
        />
      </div>
    )
  }

  return <MainApp />
}

function PublicAuthLanding({
  onSignIn,
  onSignUp,
  signupNotice,
}: {
  onSignIn: () => void
  onSignUp: () => void
  signupNotice: string | null
}) {
  return (
    <div
      className="h-full overflow-auto px-4 py-6 sm:px-6 md:px-8 md:py-8"
      style={{
        background: `
          radial-gradient(1200px 600px at 20% 0%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
          radial-gradient(1000px 800px at 80% 100%, rgba(139, 92, 246, 0.15) 0%, transparent 50%),
          linear-gradient(135deg, #0F172A 0%, #111827 30%, #0B1220 60%, #1a0f3d 100%)
        `,
        minHeight: '100vh',
      }}
    >
      <div className="mx-auto w-full max-w-7xl">
        {/* Navigation Bar */}
        <div className="mb-12 sm:mb-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
            >
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl font-bold" style={{ color: '#F9FAFB' }}>
                MARS PaperPulse
              </h1>
              <p className="text-[10px] sm:text-xs" style={{ color: 'rgba(107, 114, 128, 1)' }}>
                AI Research Assistant
              </p>
            </div>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid items-start gap-6 md:grid-cols-[1.3fr_1fr] lg:gap-8">
          {/* Left: Hero Section */}
          <section className="space-y-8">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 rounded-full border px-3.5 py-2 backdrop-blur-sm"
              style={{
                borderColor: 'rgba(59, 130, 246, 0.3)',
                backgroundColor: 'rgba(59, 130, 246, 0.08)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#3B82F6' }} />
              <span className="text-xs font-medium" style={{ color: 'rgba(147, 197, 253, 1)' }}>
                Powered by Advanced AI
              </span>
            </div>

            {/* Main Headline */}
            <div className="space-y-4">
              <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight tracking-tighter"
                style={{ color: '#F9FAFB' }}
              >
                From Data to{' '}
                <span style={{
                  background: 'linear-gradient(120deg, #8b5cf6 0%, #6366f1 50%, #4f46e5 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}>
                  Research Papers
                </span>
              </h2>
              <p className="text-base sm:text-lg leading-relaxed max-w-2xl"
                style={{ color: 'rgba(203, 213, 225, 0.9)' }}
              >
                Automate your entire research workflow. Upload data, generate ideas, develop methodology, run experiments, and produce publication-ready LaTeX papers—all guided by intelligent AI orchestration.
              </p>
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 pt-4">
              <button
                onClick={onSignIn}
                className="group flex items-center justify-center gap-2 px-8 py-3.5 rounded-lg text-sm font-semibold text-white transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] shadow-lg"
                style={{
                  background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                  boxShadow: '0 8px 32px rgba(99, 102, 241, 0.35)',
                }}
              >
                <span>Sign In</span>
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
              <button
                onClick={onSignUp}
                className="flex items-center justify-center gap-2 px-8 py-3.5 rounded-lg text-sm font-semibold transition-all duration-200"
                style={{
                  color: '#F9FAFB',
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                }}
              >
                <span>Create Account</span>
              </button>
            </div>

            {/* Key Features Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-8">
              {[
                {
                  icon: Sparkles,
                  title: '5-Stage Pipeline',
                  desc: 'Automated workflow from data to publication',
                  color: 'rgba(139, 92, 246, 1)',
                },
                {
                  icon: Layers3,
                  title: 'Multi-LLM Support',
                  desc: 'GPT-4, Claude, and more options',
                  color: 'rgba(34, 197, 94, 1)',
                },
                {
                  icon: BadgeCheck,
                  title: 'Admin Governance',
                  desc: 'Controlled access with approval workflow',
                  color: 'rgba(59, 130, 246, 1)',
                },
                {
                  icon: Activity,
                  title: 'Real-time Tracking',
                  desc: 'Monitor progress and view outputs live',
                  color: 'rgba(245, 158, 11, 1)',
                },
              ].map((feature, idx) => {
                const FeatureIcon = feature.icon
                return (
                  <div
                    key={idx}
                    className="p-4 rounded-lg border backdrop-blur-sm group hover:border-opacity-100 transition-all"
                    style={{
                      backgroundColor: 'rgba(255, 255, 255, 0.03)',
                      borderColor: 'rgba(255, 255, 255, 0.1)',
                    }}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className="w-9 h-9 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5"
                        style={{
                          backgroundColor: `${feature.color}15`,
                        }}
                      >
                        <FeatureIcon className="w-4 h-4" style={{ color: feature.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-semibold" style={{ color: '#F9FAFB' }}>
                          {feature.title}
                        </h3>
                        <p className="text-xs mt-1 leading-snug" style={{ color: 'rgba(156, 163, 175, 1)' }}>
                          {feature.desc}
                        </p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          {/* Right: Auth Card */}
          <section>
            <div
              className="rounded-xl border shadow-2xl overflow-hidden backdrop-blur-xl sticky top-6"
              style={{
                backgroundColor: 'rgba(20, 28, 47, 0.7)',
                borderColor: 'rgba(255, 255, 255, 0.1)',
              }}
            >
              <div className="p-6 sm:p-8">
                {/* Header */}
                <div className="mb-6">
                  <h2 className="text-2xl sm:text-3xl font-bold mb-2" style={{ color: '#F9FAFB' }}>
                    Welcome Back
                  </h2>
                  <p className="text-sm" style={{ color: 'rgba(156, 163, 175, 1)' }}>
                    Sign in to your research workspace or request access today.
                  </p>
                </div>

                {/* Signup Notice */}
                {signupNotice && (
                  <div
                    className="mb-6 p-4 rounded-lg border text-sm"
                    style={{
                      backgroundColor: 'rgba(34, 197, 94, 0.08)',
                      borderColor: 'rgba(34, 197, 94, 0.3)',
                      color: 'rgba(134, 239, 172, 1)',
                    }}
                  >
                    ✓ {signupNotice}
                  </div>
                )}

                {/* Auth Buttons */}
                <div className="space-y-3">
                  <button
                    onClick={onSignIn}
                    className="w-full py-3 rounded-lg text-sm font-semibold text-white transition-all duration-200 hover:shadow-lg"
                    style={{
                      background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                      boxShadow: '0 4px 16px rgba(99, 102, 241, 0.25)',
                    }}
                  >
                    Sign In
                  </button>
                  <button
                    onClick={onSignUp}
                    className="w-full py-3 rounded-lg text-sm font-semibold border transition-all duration-200"
                    style={{
                      color: '#F9FAFB',
                      backgroundColor: 'rgba(255, 255, 255, 0.05)',
                      borderColor: 'rgba(255, 255, 255, 0.15)',
                    }}
                  >
                    Create New Account
                  </button>
                </div>

                {/* Divider */}
                <div className="my-6" style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', height: '1px' }} />

                {/* Info Cards */}
                <div className="space-y-3">
                  {[
                    { icon: '⚡', title: 'Quick Setup', desc: 'Get started in minutes' },
                    { icon: '🔒', title: 'Secure', desc: 'Enterprise-grade encryption' },
                    { icon: '📊', title: 'Scalable', desc: 'Handle any project size' },
                  ].map((item, idx) => (
                    <div key={idx} className="flex gap-3">
                      <span className="text-lg flex-shrink-0">{item.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium" style={{ color: '#F9FAFB' }}>
                          {item.title}
                        </p>
                        <p className="text-[11px]" style={{ color: 'rgba(156, 163, 175, 1)' }}>
                          {item.desc}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Footer Note */}
                <div
                  className="mt-6 pt-6 text-center text-xs border-t"
                  style={{
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    color: 'rgba(107, 114, 128, 1)',
                  }}
                >
                  New accounts require admin approval before access is granted.
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Bottom Stats */}
        <div className="mt-16 sm:mt-24 pt-12 border-t grid grid-cols-2 sm:grid-cols-4 gap-8"
          style={{ borderColor: 'rgba(255, 255, 255, 0.1)' }}
        >
          {[
            { label: '5', desc: 'Research Stages' },
            { label: '10+', desc: 'LLM Providers' },
            { label: '100%', desc: 'Automated' },
            { label: '∞', desc: 'Scalable' },
          ].map((stat, idx) => (
            <div key={idx} className="text-center">
              <div
                className="text-2xl sm:text-3xl font-bold"
                style={{
                  background: 'linear-gradient(120deg, #8b5cf6, #6366f1)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                {stat.label}
              </div>
              <p className="text-xs sm:text-sm mt-2" style={{ color: 'rgba(156, 163, 175, 1)' }}>
                {stat.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Main App (authenticated users only) ───

function MainApp() {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [showTask, setShowTask] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { width, startResizing, containerRef } = useResizableSidebar()
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Auto-collapse sidebar on small screens
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    if (mq.matches) setSidebarOpen(false)
    const handler = (e: MediaQueryListEvent) => setSidebarOpen(!e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Fetch all sessions (recent + completed + failed) — authenticated
  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiCall<SessionItem[]>('/api/deepresearch/recent?include_all=true')
      setSessions(data)
    } catch {
      // ignore — auth errors handled inside apiCall
    }
  }, [])

  useEffect(() => {
    fetchSessions()
    pollRef.current = setInterval(fetchSessions, 10000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchSessions])

  useEffect(() => {
    if (!showTask) fetchSessions()
  }, [showTask, fetchSessions])

  const handleNewSession = useCallback(() => {
    setActiveTaskId(null)
    setShowTask(true)
  }, [])

  const handleSelectSession = useCallback((taskId: string) => {
    setActiveTaskId(taskId)
    setShowTask(true)
  }, [])

  const handleBack = useCallback(() => {
    setShowTask(false)
    setActiveTaskId(null)
  }, [])

  const handleDeleteSession = useCallback(async (taskId: string) => {
    if (!confirm('Delete this session? This will remove all data and files.')) return
    try {
      await apiCall(`/api/deepresearch/${taskId}`, { method: 'DELETE' })
      setSessions(prev => prev.filter(s => s.task_id !== taskId))
      if (activeTaskId === taskId) {
        setShowTask(false)
        setActiveTaskId(null)
      }
    } catch {
      // ignore
    }
  }, [activeTaskId])

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar — pass UserMenu as right slot */}
      <TopBar onNewSession={handleNewSession} rightSlot={<UserMenu />} />

      {/* Main Content + Sidebar */}
      <div className="flex-1 flex min-h-0 relative">
        <div className="flex-1 min-h-0 overflow-auto relative">
          {showTask ? (
            <DeepresearchResearchTask
              key={activeTaskId || 'new'}
              onBack={handleBack}
              resumeTaskId={activeTaskId}
            />
          ) : (
            <SimpleDashboardLanding onNewSession={handleNewSession} />
          )}

          {/* Sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(prev => !prev)}
            className="absolute top-3 right-3 p-1.5 rounded-lg transition-all duration-150
              hover:bg-[var(--mars-color-surface-overlay)] z-10"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            title={sidebarOpen ? 'Hide sessions' : 'Show sessions'}
          >
            {sidebarOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
          </button>
        </div>

        {/* Right Sidebar - with resizable container */}
        <div
          ref={containerRef}
          className="transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0"
          style={{ 
            width: sidebarOpen ? `${width}px` : '0px', 
            minWidth: sidebarOpen ? `${width}px` : '0px',
          }}
        >
          <SessionSidebar
            sessions={sessions}
            activeSessionId={activeTaskId}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
            width={width}
            onStartResize={startResizing}
          />
        </div>
      </div>
    </div>
  )
}

// ─── Welcome View (Legacy - kept for reference) ───
// Now using SimpleDashboardLanding instead

function WelcomeView_DEPRECATED({ onNewSession }: { onNewSession: () => void }) {
  return (
    <div
      className="h-full flex items-center justify-center p-6 sm:p-8"
      style={{
        background: 'linear-gradient(135deg, #0F172A 0%, #111827 25%, #0B1220 50%, #1F0F3D 100%)',
        position: 'relative',
      }}
    >
      {/* Animated background gradients */}
      <div
        className="absolute inset-0 overflow-hidden pointer-events-none"
        style={{
          background: `
            radial-gradient(900px 420px at 82% -5%, rgba(99, 102, 241, 0.15), transparent),
            radial-gradient(840px 380px at 8% 100%, rgba(139, 92, 246, 0.12), transparent)
          `,
        }}
      />

      <div className="relative z-10 max-w-5xl w-full">
        {/* Main Grid */}
        <div className="grid gap-8 lg:grid-cols-[1.2fr_1fr]">
          {/* Left Section - Content */}
          <section className="space-y-8">
            {/* Badge */}
            <div className="inline-flex items-center gap-2.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-2 backdrop-blur-sm">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              <span
                className="text-sm font-medium"
                style={{ color: 'rgba(147, 197, 253, 1)' }}
              >
                AI-Powered Research Platform
              </span>
            </div>

            {/* Heading */}
            <div className="space-y-4">
              <h1
                className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight tracking-tight"
                style={{ color: '#F9FAFB' }}
              >
                From Data to{' '}
                <span
                  style={{
                    background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                  }}
                >
                  Discovery
                </span>
              </h1>
              <p
                className="text-lg sm:text-xl text-slate-200/80 leading-relaxed max-w-2xl"
              >
                Transform complex research into publication-ready papers through our intelligent 5-stage pipeline. Upload data, refine methods, execute experiments, and generate LaTeX-formatted reports—all in one place.
              </p>
            </div>

            {/* CTA Button */}
            <button
              onClick={onNewSession}
              className="group flex items-center gap-3 px-8 py-3.5 rounded-lg text-base font-semibold text-white shadow-lg transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                boxShadow: '0 8px 24px rgba(99, 102, 241, 0.4)',
              }}
            >
              <FileText className="w-5 h-5" />
              Start New Research
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>

            {/* Quick Stats */}
            <div className="grid grid-cols-3 gap-4 pt-4">
              {[
                { label: '5 Stages', value: '100% Automated' },
                { label: 'Multiple LLMs', value: 'GPT-4 & More' },
                { label: 'LaTeX Output', value: 'Publication Ready' },
              ].map((stat) => (
                <div key={stat.label} className="space-y-1">
                  <div
                    className="text-sm font-semibold"
                    style={{ color: '#8b5cf6' }}
                  >
                    {stat.label}
                  </div>
                  <div
                    className="text-xs"
                    style={{ color: 'rgba(107, 114, 128, 1)' }}
                  >
                    {stat.value}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Right Section - Features Card */}
          <section
            className="rounded-2xl border overflow-hidden shadow-2xl backdrop-blur-xl"
            style={{
              backgroundColor: 'rgba(20, 28, 47, 0.7)',
              borderColor: 'rgba(255, 255, 255, 0.1)',
            }}
          >
            <div
              className="px-6 sm:px-8 py-8 space-y-6"
            >
              <h2
                className="text-2xl font-bold"
                style={{ color: '#F9FAFB' }}
              >
                Platform Highlights
              </h2>

              {/* Feature List */}
              <div className="space-y-4">
                {[
                  {
                    icon: Sparkles,
                    title: 'Intelligent Orchestration',
                    desc: 'AI-guided research workflow with human review checkpoints',
                    color: 'rgba(139, 92, 246, 1)',
                  },
                  {
                    icon: Layers3,
                    title: '5-Stage Pipeline',
                    desc: 'Idea generation → Methods → Experiments → Report → LaTeX',
                    color: 'rgba(34, 197, 94, 1)',
                  },
                  {
                    icon: Activity,
                    title: 'Real-time Tracking',
                    desc: 'Monitor execution progress and artifact generation',
                    color: 'rgba(245, 158, 11, 1)',
                  },
                  {
                    icon: BadgeCheck,
                    title: 'Governance Ready',
                    desc: 'Admin approval system for controlled access',
                    color: 'rgba(59, 130, 246, 1)',
                  },
                ].map((feature, idx) => {
                  const FeatureIcon = feature.icon
                  return (
                    <div key={idx} className="flex gap-4">
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{
                          backgroundColor: `${feature.color}20`,
                        }}
                      >
                        <FeatureIcon
                          className="w-5 h-5"
                          style={{ color: feature.color }}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3
                          className="font-medium text-sm"
                          style={{ color: '#F9FAFB' }}
                        >
                          {feature.title}
                        </h3>
                        <p
                          className="text-xs mt-0.5 leading-snug"
                          style={{ color: 'rgba(156, 163, 175, 1)' }}
                        >
                          {feature.desc}
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Footer Note */}
              <div
                className="mt-6 pt-6 border-t"
                style={{ borderColor: 'rgba(255, 255, 255, 0.1)' }}
              >
                <p
                  className="text-xs text-center"
                  style={{ color: 'rgba(107, 114, 128, 1)' }}
                >
                  New to PaperPulse? Account requests are reviewed by administrators.
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
