'use client'

import React, { useState, useRef, useEffect } from 'react'
import { X, Mail, Lock, LogIn, AlertCircle, Loader2 } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface LoginModalProps {
  open: boolean
  onClose: () => void
  onSwitchToSignup: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LoginModal({ open, onClose, onSwitchToSignup }: LoginModalProps) {
  const { login } = useAuth()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  const emailRef = useRef<HTMLInputElement>(null)

  // Focus first input when modal opens
  useEffect(() => {
    if (open) {
      setError(null)
      setTimeout(() => emailRef.current?.focus(), 50)
    }
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password) return
    setError(null)
    setLoading(true)
    try {
      await login(email.trim(), password)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-title"
        className="relative w-full max-w-md rounded-mars-lg shadow-mars-xl flex flex-col
          animate-[mars-scale-in_var(--mars-duration-normal)_var(--mars-ease-standard)]"
        style={{
          backgroundColor: 'var(--mars-color-surface-raised)',
          border: '1px solid var(--mars-color-border)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-0">
          <div>
            <h2 id="login-title" className="text-xl font-semibold" style={{ color: 'var(--mars-color-text)' }}>
              Sign in
            </h2>
            <p className="mt-0.5 text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>Welcome back to MARS PaperPulse</p>
          </div>
          <button
            onClick={onClose}
            className="mars-focus-ring p-1.5 rounded-mars-md transition-colors hover:bg-[var(--mars-color-bg-hover)] hover:text-[var(--mars-color-text)]"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate className="px-6 py-6 flex flex-col gap-4">
          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-email" className="text-sm font-medium" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Email address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <input
                ref={emailRef}
                id="login-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="mars-input w-full pl-10 pr-4 py-2.5 rounded-mars-md text-sm transition-colors"
              />
            </div>
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-password" className="text-sm font-medium" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="mars-input w-full pl-10 pr-4 py-2.5 rounded-mars-md text-sm transition-colors"
              />
            </div>
          </div>

          {/* Error banner */}
          {error && (
            <div
              className="flex items-start gap-2.5 px-4 py-3 rounded-mars-md text-sm"
              style={{
                backgroundColor: 'var(--mars-color-danger-subtle)',
                border: '1px solid color-mix(in srgb, var(--mars-color-danger) 40%, transparent)',
                color: 'var(--mars-color-danger)',
              }}
            >
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !email.trim() || !password}
            className="mars-focus-ring flex items-center justify-center gap-2 w-full py-2.5 rounded-mars-md
              text-sm font-semibold text-white bg-brand-gradient shadow-glow-sm
              hover:-translate-y-px hover:shadow-glow active:translate-y-0
              disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0
              transition-all duration-mars-fast ease-mars"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogIn className="w-4 h-4" />
            )}
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {/* Footer */}
        <div className="px-6 pb-6 text-center text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
          Don&apos;t have an account?{' '}
          <button
            onClick={() => { setError(null); onSwitchToSignup() }}
            className="font-medium underline underline-offset-2 transition-colors hover:opacity-80"
            style={{ color: 'var(--mars-color-primary-text)' }}
          >
            Sign up
          </button>
        </div>
      </div>
    </div>
  )
}
