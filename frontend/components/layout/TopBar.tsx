'use client'

import { useState } from 'react'
import { Sun, Moon, Plus, Settings } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import ProviderSettings from '@/components/settings/ProviderSettings'

interface TopBarProps {
  onNewSession: () => void
}

export default function TopBar({ onNewSession }: TopBarProps) {
  const { theme, toggleTheme } = useTheme()
  const [showSettings, setShowSettings] = useState(false)

  return (
    <>
      <header
        className="relative flex-shrink-0 border-b"
        style={{
          backgroundColor: 'var(--mars-color-surface-raised)',
          borderColor: 'var(--mars-color-border)',
        }}
        role="banner"
      >
        {/* Subtle gradient sheen across the top edge */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background: 'linear-gradient(90deg, transparent 0%, rgba(139,92,246,0.5) 30%, rgba(99,102,241,0.5) 70%, transparent 100%)',
          }}
        />
        <div
          className="flex items-center justify-between px-5"
          style={{ height: '56px' }}
        >
          {/* Left: App Name */}
          <div className="flex items-center gap-3">
            <div className="relative">
              {/* Soft glow halo behind logo */}
              <div
                aria-hidden
                className="absolute -inset-1 rounded-xl blur-md opacity-60"
                style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
              />
              <div
                className="relative w-9 h-9 rounded-xl flex items-center justify-center mars-gradient-animated"
                style={{
                  boxShadow: '0 4px 12px rgba(99, 102, 241, 0.45), inset 0 1px 0 rgba(255,255,255,0.2)',
                }}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <line x1="10" y1="9" x2="8" y2="9" />
                </svg>
              </div>
            </div>
            <div className="leading-tight">
              <h1
                className="text-[15px] font-semibold tracking-tight"
                style={{ color: 'var(--mars-color-text)', fontFamily: 'var(--mars-font-sans)' }}
              >
                MARS <span className="mx-0.5" style={{ color: 'var(--mars-color-text-tertiary)' }}>·</span>{' '}
                <span style={{ color: 'var(--mars-color-text)' }}>PaperPulse</span>
              </h1>
              <p className="text-[10.5px] mt-0.5" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                AI Research Paper Generation
              </p>
            </div>
          </div>

          {/* Right: Settings + Theme toggle + New Session */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 rounded-lg transition-all duration-150
                hover:bg-[var(--mars-color-bg-hover)] hover:scale-[1.05] active:scale-[0.95]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              aria-label="LLM Provider Settings"
              title="LLM Provider Settings"
            >
              <Settings className="w-4 h-4" />
            </button>

            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg transition-all duration-150
                hover:bg-[var(--mars-color-bg-hover)] hover:scale-[1.05] active:scale-[0.95]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            <button
              onClick={onNewSession}
              className="mars-shimmer-btn flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold
                text-white transition-all duration-150 hover:shadow-lg hover:scale-[1.04] active:scale-[0.97]"
              style={{
                background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                boxShadow: '0 4px 14px rgba(99, 102, 241, 0.40), inset 0 1px 0 rgba(255,255,255,0.18)',
              }}
            >
              <Plus className="w-3.5 h-3.5" />
              New Session
            </button>
          </div>
        </div>
      </header>

      {/* Provider Settings Modal */}
      {showSettings && (
        <ProviderSettings onClose={() => setShowSettings(false)} />
      )}
    </>
  )
}
