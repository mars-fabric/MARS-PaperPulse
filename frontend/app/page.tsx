'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { FileText, Sparkles, Upload, PanelRightClose, PanelRightOpen } from 'lucide-react'
import TopBar from '@/components/layout/TopBar'
import SessionSidebar from '@/components/sessions/SessionSidebar'
import type { SessionItem } from '@/components/sessions/SessionSidebar'
import DeepresearchResearchTask from '@/components/tasks/DeepresearchResearchTask'
import { getApiUrl } from '@/lib/config'

const SIDEBAR_MIN_WIDTH = 240
const SIDEBAR_DEFAULT_WIDTH = 300
const SIDEBAR_WIDTH_KEY = 'paperpulse:sidebar-width'

export default function Home() {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [showTask, setShowTask] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState<number>(SIDEBAR_DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Restore persisted sidebar width
  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_WIDTH_KEY)
    if (stored) {
      const n = parseInt(stored, 10)
      if (!Number.isNaN(n)) setSidebarWidth(n)
    }
  }, [])

  // Auto-collapse sidebar on small screens
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    if (mq.matches) setSidebarOpen(false)
    const handler = (e: MediaQueryListEvent) => setSidebarOpen(!e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Drag-to-resize sidebar (clamped between min and half-screen)
  useEffect(() => {
    if (!isResizing) return
    const handleMove = (e: MouseEvent) => {
      const fromRight = window.innerWidth - e.clientX
      const max = Math.floor(window.innerWidth / 2)
      const next = Math.max(SIDEBAR_MIN_WIDTH, Math.min(max, fromRight))
      setSidebarWidth(next)
    }
    const handleUp = () => {
      setIsResizing(false)
      try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth)) } catch {}
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [isResizing, sidebarWidth])

  // Fetch all sessions (recent + completed + failed)
  const fetchSessions = useCallback(async () => {
    try {
      const resp = await fetch(getApiUrl('/api/deepresearch/recent?include_all=true'))
      if (resp.ok) {
        const data: SessionItem[] = await resp.json()
        setSessions(data)
      }
    } catch {
      // ignore
    }
  }, [])

  // Poll sessions periodically to keep sidebar up to date
  useEffect(() => {
    fetchSessions()
    pollRef.current = setInterval(fetchSessions, 10000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchSessions])

  // Refresh sessions when task view is closed
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
      const resp = await fetch(getApiUrl(`/api/deepresearch/${taskId}`), { method: 'DELETE' })
      if (!resp.ok) {
        let detail = `HTTP ${resp.status}`
        try {
          const body = await resp.json()
          if (body?.detail) detail = String(body.detail)
        } catch {}
        alert(`Failed to delete session: ${detail}`)
        return
      }
      setSessions(prev => prev.filter(s => s.task_id !== taskId))
      if (activeTaskId === taskId) {
        setShowTask(false)
        setActiveTaskId(null)
      }
      // Re-sync from server so a slow delete can't be undone by the 10s poll.
      fetchSessions()
    } catch (err) {
      alert(`Failed to delete session: ${err instanceof Error ? err.message : String(err)}`)
    }
  }, [activeTaskId, fetchSessions])

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar */}
      <TopBar onNewSession={handleNewSession} />

      {/* Main Content + Sidebar */}
      <div className="flex-1 flex min-h-0 relative">
        {/* Main Content Area */}
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

          {/* Sidebar Toggle Button (floating) */}
          <button
            onClick={() => setSidebarOpen(prev => !prev)}
            className="absolute top-3 right-3 p-1.5 rounded-lg transition-all duration-150
              hover:bg-[var(--mars-color-surface-overlay)] z-10"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            title={sidebarOpen ? 'Hide sessions' : 'Show sessions'}
          >
            {sidebarOpen ? (
              <PanelRightClose className="w-4 h-4" />
            ) : (
              <PanelRightOpen className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Resize handle (only when sidebar is open) */}
        {sidebarOpen && (
          <div
            role="separator"
            aria-label="Resize sessions panel"
            aria-orientation="vertical"
            onMouseDown={(e) => { e.preventDefault(); setIsResizing(true) }}
            onDoubleClick={() => {
              setSidebarWidth(SIDEBAR_DEFAULT_WIDTH)
              try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(SIDEBAR_DEFAULT_WIDTH)) } catch {}
            }}
            className="group relative w-1.5 flex-shrink-0 cursor-col-resize transition-colors duration-150"
            style={{
              backgroundColor: isResizing
                ? 'var(--mars-color-primary)'
                : 'transparent',
            }}
            title="Drag to resize · Double-click to reset"
          >
            {/* Hover highlight */}
            <div
              aria-hidden
              className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px transition-all duration-150 group-hover:w-1"
              style={{
                backgroundColor: isResizing
                  ? 'var(--mars-color-primary)'
                  : 'var(--mars-color-border)',
              }}
            />
            {/* Grab indicator dots */}
            <div
              aria-hidden
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="w-0.5 h-0.5 rounded-full"
                  style={{ backgroundColor: 'var(--mars-color-text-secondary)' }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Right Sidebar - Session List */}
        <div
          className={isResizing ? 'overflow-hidden' : 'transition-all duration-300 ease-in-out overflow-hidden'}
          style={{
            width: sidebarOpen ? `${sidebarWidth}px` : '0px',
            minWidth: sidebarOpen ? `${sidebarWidth}px` : '0px',
          }}
        >
          <SessionSidebar
            sessions={sessions}
            activeSessionId={activeTaskId}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
            width={sidebarWidth}
          />
        </div>
      </div>
    </div>
  )
}

// ─── Welcome View (shown when no task is active) ───

interface WelcomeViewProps {
  onNewSession: () => void
}

function WelcomeView({ onNewSession }: WelcomeViewProps) {
  const features = [
    { icon: Upload, label: 'Upload Data', desc: 'CSV, PDF, Text files', accent: '#22c55e' },
    { icon: Sparkles, label: 'AI Stages', desc: '4-phase pipeline', accent: '#8b5cf6' },
    { icon: FileText, label: 'LaTeX Paper', desc: 'Publication ready', accent: '#3b82f6' },
  ]

  return (
    <div className="relative h-full flex items-center justify-center p-8 overflow-hidden">
      {/* Aurora background blobs */}
      <div className="mars-aurora-bg" aria-hidden />

      {/* Twinkling decorative dots */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden>
        {[
          { top: '12%', left: '18%', size: 4, delay: '0s' },
          { top: '22%', left: '78%', size: 3, delay: '0.6s' },
          { top: '70%', left: '12%', size: 5, delay: '1.2s' },
          { top: '80%', left: '85%', size: 3, delay: '0.3s' },
          { top: '40%', left: '8%', size: 2, delay: '1.8s' },
          { top: '55%', left: '92%', size: 4, delay: '0.9s' },
        ].map((dot, i) => (
          <span
            key={i}
            className="mars-twinkle absolute rounded-full"
            style={{
              top: dot.top,
              left: dot.left,
              width: dot.size,
              height: dot.size,
              background: 'linear-gradient(135deg, #a78bfa, #60a5fa)',
              animationDelay: dot.delay,
              boxShadow: '0 0 8px rgba(139, 92, 246, 0.6)',
            }}
          />
        ))}
      </div>

      <div className="relative z-10 max-w-lg w-full text-center">
        {/* Hero Icon */}
        <div className="relative w-24 h-24 mx-auto mb-6">
          {/* Soft halo behind the icon */}
          <div
            className="absolute inset-0 rounded-3xl blur-2xl opacity-70"
            style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.6), transparent 70%)' }}
            aria-hidden
          />
          <div
            className="relative mars-glow mars-float w-24 h-24 rounded-3xl flex items-center justify-center mars-anim-bounce-in"
            style={{
              background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 50%, #4f46e5 100%)',
            }}
          >
            <Sparkles className="w-11 h-11 text-white drop-shadow-lg" />
          </div>
        </div>

        {/* Title */}
        <h2
          className="text-4xl font-bold mb-3 tracking-tight mars-anim-slide-up"
          style={{ color: 'var(--mars-color-text)' }}
        >
          PaperPulse
        </h2>
        <p
          className="text-sm mb-10 mars-anim-slide-up mars-delay-100 leading-relaxed max-w-md mx-auto"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Generate deep scientific research papers through AI-powered interactive stages
        </p>

        {/* New Session CTA */}
        <button
          onClick={onNewSession}
          className="mars-shimmer-btn mars-anim-slide-up mars-delay-200 inline-flex items-center gap-3 px-7 py-3.5 rounded-2xl text-sm font-semibold
            text-white transition-all duration-200 hover:shadow-2xl hover:scale-[1.03] active:scale-[0.98]"
          style={{
            background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            boxShadow: '0 8px 28px rgba(99, 102, 241, 0.45), inset 0 1px 0 rgba(255,255,255,0.18)',
          }}
        >
          <FileText className="w-5 h-5" />
          Start New Research
          <span className="opacity-70 -mr-1">→</span>
        </button>

        {/* Quick features */}
        <div className="grid grid-cols-3 gap-4 mt-12">
          {features.map((feature, idx) => (
            <div
              key={feature.label}
              className={`mars-card-tilt mars-anim-slide-up mars-delay-${(idx + 3) * 100} relative p-4 rounded-2xl text-left overflow-hidden`}
              style={{
                backgroundColor: 'var(--mars-color-surface-raised)',
                border: '1px solid var(--mars-color-border)',
              }}
            >
              <div
                className="w-9 h-9 rounded-xl mb-2.5 flex items-center justify-center"
                style={{
                  background: `linear-gradient(135deg, ${feature.accent}33, ${feature.accent}11)`,
                  border: `1px solid ${feature.accent}40`,
                }}
              >
                <feature.icon className="w-4 h-4" style={{ color: feature.accent }} />
              </div>
              <p className="text-xs font-semibold mb-0.5" style={{ color: 'var(--mars-color-text)' }}>
                {feature.label}
              </p>
              <p className="text-[10px] leading-snug" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
