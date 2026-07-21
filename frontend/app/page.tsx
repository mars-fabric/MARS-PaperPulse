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
import { useAuth } from '@/contexts/AuthContext'
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
      className="h-full overflow-auto px-4 py-8 sm:px-6 md:px-10 md:py-10"
      style={{
        background:
          'radial-gradient(900px 420px at 82% -5%, rgba(34, 211, 238, 0.2), transparent), radial-gradient(840px 380px at 8% 100%, rgba(251, 146, 60, 0.18), transparent), linear-gradient(160deg, #020617 0%, #071123 45%, #031525 100%)',
      }}
    >
      <div className="mx-auto w-full max-w-6xl">
        <div className="grid items-stretch gap-6 md:grid-cols-[1.15fr_0.85fr]">
          <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.04] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.45)] backdrop-blur-xl sm:p-8">
            <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-16 -left-16 h-52 w-52 rounded-full bg-orange-400/20 blur-3xl" />

            <div className="relative space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-300/10 px-3 py-1 text-xs font-semibold tracking-wide text-cyan-100">
                <Sparkles className="h-3.5 w-3.5" />
                MARS PaperPulse Platform
              </div>

              <div className="space-y-3">
                <h1 className="text-3xl font-bold leading-tight text-white sm:text-5xl">
                  From Raw Evidence to Publishable Insight
                </h1>
                <p className="max-w-2xl text-sm text-slate-200/90 sm:text-base">
                  Operate complex research as a guided multi-stage system with transparent outputs, review checkpoints, and ready-to-share reports.
                </p>
              </div>

              <div className="grid gap-3 text-xs sm:grid-cols-3 sm:text-sm">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 text-slate-100 transition-transform duration-200 hover:-translate-y-0.5">
                  <div className="mb-1.5 flex items-center gap-2 text-cyan-200">
                    <Layers3 className="h-4 w-4" />
                    5-Stage Pipeline
                  </div>
                  Structured execution from ingestion through report packaging.
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 text-slate-100 transition-transform duration-200 hover:-translate-y-0.5">
                  <div className="mb-1.5 flex items-center gap-2 text-emerald-200">
                    <BadgeCheck className="h-4 w-4" />
                    Review-Ready
                  </div>
                  Consistent outputs with audit-friendly status tracking.
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 text-slate-100 transition-transform duration-200 hover:-translate-y-0.5">
                  <div className="mb-1.5 flex items-center gap-2 text-orange-200">
                    <Activity className="h-4 w-4" />
                    Observability
                  </div>
                  Tracing support for reproducible, explainable workflows.
                </div>
              </div>

              <div className="rounded-2xl border border-cyan-200/20 bg-slate-950/35 p-4">
                <div className="grid gap-3 text-xs text-slate-200 sm:grid-cols-3 sm:text-sm">
                  <div>
                    <p className="text-cyan-200">Adaptive Orchestration</p>
                    <p className="mt-0.5 text-slate-300">Task-aware routing across the research lifecycle.</p>
                  </div>
                  <div>
                    <p className="text-emerald-200">Human-in-the-Loop</p>
                    <p className="mt-0.5 text-slate-300">Admin approval and governance for account access.</p>
                  </div>
                  <div>
                    <p className="text-orange-200">Publication Outputs</p>
                    <p className="mt-0.5 text-slate-300">Auto-generated report artifacts and summaries.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <aside className="rounded-3xl border border-white/10 bg-slate-900/85 p-6 shadow-[0_24px_64px_rgba(0,0,0,0.45)] backdrop-blur md:p-7">
            <h2 className="text-2xl font-semibold text-white">Welcome</h2>
            <p className="mt-1.5 text-sm text-slate-300">Sign in to continue your research workspace, or request a new account.</p>

            {signupNotice && (
              <div className="mt-4 rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                {signupNotice}
              </div>
            )}

            <div className="mt-6 space-y-3">
              <button
                onClick={onSignIn}
                className="group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 via-sky-500 to-blue-500 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-900/35 transition-all duration-200 hover:scale-[1.01] hover:from-cyan-400 hover:via-sky-400 hover:to-blue-400"
              >
                Sign In
                <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
              </button>
              <button
                onClick={onSignUp}
                className="w-full rounded-xl border border-slate-600 bg-slate-800/75 py-2.5 text-sm font-semibold text-slate-100 transition-colors hover:bg-slate-700/80"
              >
                Create Account
              </button>
            </div>

            <div className="mt-6 rounded-xl border border-slate-700/70 bg-slate-800/45 p-3.5 text-xs text-slate-300">
              New accounts are reviewed by an administrator before access is granted.
            </div>
          </aside>
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
            <WelcomeView onNewSession={handleNewSession} />
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

        {/* Right Sidebar */}
        <div
          className="transition-all duration-300 ease-in-out overflow-hidden"
          style={{ width: sidebarOpen ? '280px' : '0px', minWidth: sidebarOpen ? '280px' : '0px' }}
        >
          <SessionSidebar
            sessions={sessions}
            activeSessionId={activeTaskId}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
          />
        </div>
      </div>
    </div>
  )
}

// ─── Welcome View ───

function WelcomeView({ onNewSession }: { onNewSession: () => void }) {
  return (
    <div className="h-full flex items-center justify-center p-8">
      <div className="max-w-lg w-full text-center">
        <div
          className="w-20 h-20 rounded-2xl mx-auto mb-6 flex items-center justify-center"
          style={{
            background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 50%, #4f46e5 100%)',
            boxShadow: '0 8px 32px rgba(99, 102, 241, 0.3)',
          }}
        >
          <Sparkles className="w-10 h-10 text-white" />
        </div>
        <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--mars-color-text)' }}>
          PaperPulse
        </h2>
        <p className="text-sm mb-8" style={{ color: 'var(--mars-color-text-secondary)' }}>
          Generate deep scientific research papers through AI-powered interactive stages
        </p>
        <button
          onClick={onNewSession}
          className="inline-flex items-center gap-3 px-6 py-3 rounded-xl text-sm font-semibold
            text-white transition-all duration-200 hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
          style={{
            background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            boxShadow: '0 4px 16px rgba(99, 102, 241, 0.3)',
          }}
        >
          <FileText className="w-5 h-5" />
          Start New Research
        </button>
        <div className="grid grid-cols-3 gap-4 mt-10">
          {[
            { icon: Upload, label: 'Upload Data', desc: 'CSV, PDF, Text files' },
            { icon: Sparkles, label: 'AI Stages', desc: '4-phase pipeline' },
            { icon: FileText, label: 'LaTeX Paper', desc: 'Publication ready' },
          ].map((feature) => (
            <div
              key={feature.label}
              className="p-3 rounded-xl"
              style={{ backgroundColor: 'var(--mars-color-surface)', border: '1px solid var(--mars-color-border)' }}
            >
              <feature.icon className="w-5 h-5 mx-auto mb-1.5" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <p className="text-xs font-medium" style={{ color: 'var(--mars-color-text)' }}>{feature.label}</p>
              <p className="text-[10px]" style={{ color: 'var(--mars-color-text-tertiary)' }}>{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
