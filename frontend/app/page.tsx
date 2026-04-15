'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { FileText, Sparkles, Upload, PanelRightClose, PanelRightOpen } from 'lucide-react'
import TopBar from '@/components/layout/TopBar'
import SessionSidebar from '@/components/sessions/SessionSidebar'
import type { SessionItem } from '@/components/sessions/SessionSidebar'
import DeepresearchResearchTask from '@/components/tasks/DeepresearchResearchTask'
import { getApiUrl } from '@/lib/config'

export default function Home() {
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
      await fetch(getApiUrl(`/api/deepresearch/${taskId}`), { method: 'DELETE' })
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

        {/* Right Sidebar - Session List */}
        <div
          className="transition-all duration-300 ease-in-out overflow-hidden"
          style={{
            width: sidebarOpen ? '280px' : '0px',
            minWidth: sidebarOpen ? '280px' : '0px',
          }}
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

// ─── Welcome View (shown when no task is active) ───

interface WelcomeViewProps {
  onNewSession: () => void
}

function WelcomeView({ onNewSession }: WelcomeViewProps) {
  return (
    <div className="h-full flex items-center justify-center p-8">
      <div className="max-w-lg w-full text-center">
        {/* Hero Icon */}
        <div
          className="w-20 h-20 rounded-2xl mx-auto mb-6 flex items-center justify-center"
          style={{
            background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 50%, #4f46e5 100%)',
            boxShadow: '0 8px 32px rgba(99, 102, 241, 0.3)',
          }}
        >
          <Sparkles className="w-10 h-10 text-white" />
        </div>

        {/* Title */}
        <h2
          className="text-2xl font-bold mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          PaperPulse
        </h2>
        <p
          className="text-sm mb-8"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Generate deep scientific research papers through AI-powered interactive stages
        </p>

        {/* New Session CTA */}
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

        {/* Quick features */}
        <div className="grid grid-cols-3 gap-4 mt-10">
          {[
            { icon: Upload, label: 'Upload Data', desc: 'CSV, PDF, Text files' },
            { icon: Sparkles, label: 'AI Stages', desc: '4-phase pipeline' },
            { icon: FileText, label: 'LaTeX Paper', desc: 'Publication ready' },
          ].map((feature) => (
            <div
              key={feature.label}
              className="p-3 rounded-xl"
              style={{
                backgroundColor: 'var(--mars-color-surface)',
                border: '1px solid var(--mars-color-border)',
              }}
            >
              <feature.icon
                className="w-5 h-5 mx-auto mb-1.5"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              />
              <p className="text-xs font-medium" style={{ color: 'var(--mars-color-text)' }}>
                {feature.label}
              </p>
              <p className="text-[10px]" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
