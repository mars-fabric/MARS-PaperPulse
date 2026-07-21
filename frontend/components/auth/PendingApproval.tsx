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
    <div className="fixed inset-0 z-40 flex flex-col items-center justify-center bg-gray-950 px-6">
      {/* Decorative background glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
        style={{
          background: 'radial-gradient(ellipse 60% 40% at 50% 50%, rgba(139,92,246,0.08) 0%, transparent 70%)',
        }}
      />

      <div className="relative flex flex-col items-center gap-6 max-w-sm text-center">
        {/* Icon */}
        <div className="flex items-center justify-center w-20 h-20 rounded-full bg-amber-500/10 border border-amber-500/30">
          <Clock className="w-9 h-9 text-amber-400" />
        </div>

        {/* Heading */}
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Account pending approval
          </h1>
          <p className="text-sm text-gray-400 leading-relaxed">
            Your account has been created and is waiting for admin approval.
          </p>
        </div>

        {/* Email pill */}
        {displayEmail && (
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-gray-800 border border-gray-700">
            <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
            <span className="text-sm text-gray-200 font-medium">{displayEmail}</span>
          </div>
        )}

        {/* Info card */}
        <div className="w-full flex flex-col gap-2 rounded-lg bg-gray-800/60 border border-gray-700/50 px-5 py-4 text-left">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">What happens next?</p>
          <ul className="flex flex-col gap-1.5">
            {[
              'An administrator will review your registration.',
              'You will gain access once your account is approved.',
              'You can check back later or contact your admin.',
            ].map(text => (
              <li key={text} className="flex items-start gap-2 text-sm text-gray-300">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-gray-500 shrink-0" />
                {text}
              </li>
            ))}
          </ul>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 w-full">
          <button
            onClick={() => window.location.reload()}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg
              text-sm font-medium text-gray-300 bg-gray-800 border border-gray-700
              hover:bg-gray-700 hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg
              text-sm font-medium text-white
              bg-gradient-to-r from-violet-600 to-indigo-600
              hover:from-violet-500 hover:to-indigo-500
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-150"
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
