'use client'

import React, { useState } from 'react'
import { Clock, LogOut, Loader2, RefreshCw } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PendingApproval() {
  const { user, logout } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await logout()
    } finally {
      setLoggingOut(false)
    }
  }

  const displayEmail = user?.email ?? ''

  return (
    <div className="fixed inset-0 z-40 flex flex-col items-center justify-center px-6" style={{ backgroundColor: 'var(--mars-color-bg)' }}>
      {/* Decorative background glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
        style={{
          background: 'radial-gradient(ellipse 60% 40% at 50% 50%, rgba(139,92,246,0.10) 0%, transparent 70%)',
        }}
      />

      <div className="relative flex flex-col items-center gap-6 max-w-sm text-center mars-animate-in">
        {/* Icon */}
        <div className="flex items-center justify-center w-20 h-20 rounded-full bg-amber-500/10 border border-amber-500/30">
          <Clock className="w-9 h-9 text-amber-400" />
        </div>

        {/* Heading */}
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--mars-color-text)' }}>
            Account pending approval
          </h1>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--mars-color-text-secondary)' }}>
            Your account has been created and is waiting for admin approval.
          </p>
        </div>

        {/* Email pill */}
        {displayEmail && (
          <div
            className="flex items-center gap-2 px-4 py-2 rounded-full"
            style={{ backgroundColor: 'var(--mars-color-surface-overlay)', border: '1px solid var(--mars-color-border)' }}
          >
            <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
            <span className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>{displayEmail}</span>
          </div>
        )}

        {/* Info card */}
        <div
          className="w-full flex flex-col gap-2 rounded-mars-lg px-5 py-4 text-left"
          style={{ backgroundColor: 'var(--mars-color-surface-raised)', border: '1px solid var(--mars-color-border)' }}
        >
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--mars-color-text-tertiary)' }}>What happens next?</p>
          <ul className="flex flex-col gap-1.5">
            {[
              'An administrator will review your registration.',
              'You will gain access once your account is approved.',
              'You can check back later or contact your admin.',
            ].map(text => (
              <li key={text} className="flex items-start gap-2 text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: 'var(--mars-color-text-tertiary)' }} />
                {text}
              </li>
            ))}
          </ul>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 w-full">
          <button
            onClick={() => window.location.reload()}
            className="mars-focus-ring flex-1 flex items-center justify-center gap-2 py-2.5 rounded-mars-md
              text-sm font-medium transition-colors hover:bg-[var(--mars-color-bg-hover)]"
            style={{ color: 'var(--mars-color-text-secondary)', backgroundColor: 'var(--mars-color-surface-overlay)', border: '1px solid var(--mars-color-border)' }}
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="mars-focus-ring flex-1 flex items-center justify-center gap-2 py-2.5 rounded-mars-md
              text-sm font-medium text-white bg-brand-gradient shadow-glow-sm
              hover:-translate-y-px hover:shadow-glow active:translate-y-0
              disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0
              transition-all duration-mars-fast ease-mars"
          >
            {loggingOut ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogOut className="w-4 h-4" />
            )}
            {loggingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </div>
    </div>
  )
}
