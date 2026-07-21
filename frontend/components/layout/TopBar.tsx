'use client'

import { useState } from 'react'
import type { ReactNode } from 'react'
import { Sun, Moon, Plus, Settings } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import ProviderSettings from '@/components/settings/ProviderSettings'

interface TopBarProps {
  onNewSession: () => void
  rightSlot?: ReactNode
}

export default function TopBar({ onNewSession, rightSlot }: TopBarProps) {
  const { theme, toggleTheme } = useTheme()
  const [showSettings, setShowSettings] = useState(false)

  return (
    <>
      <header
        className="flex-shrink-0 border-b"
        style={{
          backgroundColor: 'var(--mars-color-surface-raised)',
          borderColor: 'var(--mars-color-border)',
        }}
        role="banner"
      >
        <div
          className="flex items-center justify-between px-5"
          style={{ height: '52px' }}
        >
          {/* Left: App Name */}
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <line x1="10" y1="9" x2="8" y2="9" />
              </svg>
            </div>
            <div>
              <h1
                className="text-sm font-bold tracking-tight"
                style={{ color: 'var(--mars-color-text)', fontFamily: 'var(--mars-font-sans)' }}
              >
                MARS - PaperPulse
              </h1>
              <p className="text-[10px] leading-tight" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                Deep Scientific Research
              </p>
            </div>
          </div>

          {/* Right: Settings + Theme toggle + New Session */}
          <div className="flex items-center gap-2">
            {rightSlot}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 rounded-lg transition-colors duration-150
                hover:bg-[var(--mars-color-bg-hover)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              aria-label="LLM Provider Settings"
              title="LLM Provider Settings"
            >
              <Settings className="w-4 h-4" />
            </button>

            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg transition-colors duration-150
                hover:bg-[var(--mars-color-bg-hover)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            <button
              onClick={onNewSession}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                text-white transition-all duration-150 hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
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
