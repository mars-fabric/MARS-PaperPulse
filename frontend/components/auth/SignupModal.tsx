'use client'

import React, { useState, useRef, useEffect } from 'react'
import { X, Mail, Lock, User as UserIcon, AlertCircle, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { getApiUrl } from '@/lib/config'

// ---------------------------------------------------------------------------
// Password policy rules
// ---------------------------------------------------------------------------

interface PolicyRule {
  label: string
  test: (pw: string) => boolean
}

const POLICY: PolicyRule[] = [
  { label: 'At least 8 characters',          test: pw => pw.length >= 8 },
  { label: 'At least one uppercase letter',  test: pw => /[A-Z]/.test(pw) },
  { label: 'At least one lowercase letter',  test: pw => /[a-z]/.test(pw) },
  { label: 'At least one number',            test: pw => /\d/.test(pw) },
  { label: 'At least one special character', test: pw => /[^A-Za-z0-9]/.test(pw) },
]

function strengthLevel(pw: string): { passed: number; label: string; color: string } {
  const passed = POLICY.filter(r => r.test(pw)).length
  if (passed <= 1) return { passed, label: 'Very weak',  color: 'bg-red-500' }
  if (passed === 2) return { passed, label: 'Weak',       color: 'bg-orange-500' }
  if (passed === 3) return { passed, label: 'Fair',       color: 'bg-yellow-500' }
  if (passed === 4) return { passed, label: 'Strong',     color: 'bg-blue-500' }
  return              { passed, label: 'Very strong', color: 'bg-emerald-500' }
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SignupModalProps {
  open: boolean
  onClose: () => void
  onSwitchToLogin: () => void
  onSignedUp: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SignupModal({ open, onClose, onSwitchToLogin, onSignedUp }: SignupModalProps) {
  const [fullName, setFullName]           = useState('')
  const [email, setEmail]                 = useState('')
  const [password, setPassword]           = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError]                 = useState<string | null>(null)
  const [loading, setLoading]             = useState(false)
  const [showPolicy, setShowPolicy]       = useState(false)

  const nameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setError(null)
      setShowPolicy(false)
      setTimeout(() => nameRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  const strength = password ? strengthLevel(password) : null
  const allPolicyPassed = POLICY.every(r => r.test(password))
  const passwordsMatch  = password === confirmPassword && confirmPassword !== ''

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!allPolicyPassed) {
      setError('Password does not meet all requirements.')
      setShowPolicy(true)
      return
    }
    if (!passwordsMatch) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(getApiUrl('/api/auth/signup'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          password,
          full_name: fullName.trim() || undefined,
        }),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = body?.detail
        const msg = Array.isArray(detail)
          ? detail.map((d: any) => d?.msg || String(d)).join('; ')
          : (typeof detail === 'string' ? detail : `Registration failed (${res.status})`)
        throw new Error(msg)
      }

      onSignedUp()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.')
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
        aria-labelledby="signup-title"
        className="relative w-full max-w-md rounded-mars-lg shadow-mars-xl flex flex-col max-h-[90vh] overflow-y-auto
          animate-[mars-scale-in_var(--mars-duration-normal)_var(--mars-ease-standard)]"
        style={{
          backgroundColor: 'var(--mars-color-surface-raised)',
          border: '1px solid var(--mars-color-border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 pt-6 pb-0 sticky top-0 z-10"
          style={{ backgroundColor: 'var(--mars-color-surface-raised)' }}
        >
          <div>
            <h2 id="signup-title" className="text-xl font-semibold" style={{ color: 'var(--mars-color-text)' }}>
              Create account
            </h2>
            <p className="mt-0.5 text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>Join MARS PaperPulse</p>
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
          {/* Full name (optional) */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-name" className="text-sm font-medium" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Full name <span className="font-normal" style={{ color: 'var(--mars-color-text-tertiary)' }}>(optional)</span>
            </label>
            <div className="relative">
              <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <input
                ref={nameRef}
                id="signup-name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Jane Smith"
                className="mars-input pl-10 pr-4 py-2.5 rounded-mars-md text-sm"
              />
            </div>
          </div>

          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-email" className="text-sm font-medium" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Email address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <input
                id="signup-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="mars-input pl-10 pr-4 py-2.5 rounded-mars-md text-sm"
              />
            </div>
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-password" className="text-sm font-medium" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <input
                id="signup-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={e => { setPassword(e.target.value); setShowPolicy(true) }}
                onFocus={() => setShowPolicy(true)}
                placeholder="••••••••"
                required
                className="mars-input pl-10 pr-4 py-2.5 rounded-mars-md text-sm"
              />
            </div>

            {/* Strength bar */}
            {password && strength && (
              <div className="flex flex-col gap-1.5 mt-1">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}>
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${strength.color}`}
                      style={{ width: `${(strength.passed / POLICY.length) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs shrink-0 w-20 text-right" style={{ color: 'var(--mars-color-text-secondary)' }}>{strength.label}</span>
                </div>

                {/* Policy checklist */}
                {showPolicy && (
                  <ul className="flex flex-col gap-1 mt-0.5">
                    {POLICY.map(rule => {
                      const ok = rule.test(password)
                      return (
                        <li key={rule.label} className="flex items-center gap-1.5 text-xs">
                          {ok
                            ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                            : <XCircle className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--mars-color-text-disabled)' }} />
                          }
                          <span style={{ color: ok ? 'var(--mars-color-text-secondary)' : 'var(--mars-color-text-tertiary)' }}>
                            {rule.label}
                          </span>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            )}
          </div>

          {/* Confirm password */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-confirm" className="text-sm font-medium" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Confirm password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: 'var(--mars-color-text-tertiary)' }} />
              <input
                id="signup-confirm"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="mars-input pl-10 pr-4 py-2.5 rounded-mars-md text-sm"
                style={confirmPassword && !passwordsMatch ? { borderColor: 'var(--mars-color-danger)' } : undefined}
              />
            </div>
            {confirmPassword && !passwordsMatch && (
              <p className="text-xs" style={{ color: 'var(--mars-color-danger)' }}>Passwords do not match.</p>
            )}
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
            disabled={loading || !email.trim() || !password || !confirmPassword}
            className="mars-focus-ring flex items-center justify-center gap-2 w-full py-2.5 rounded-mars-md
              text-sm font-semibold text-white bg-brand-gradient shadow-glow-sm
              hover:-translate-y-px hover:shadow-glow active:translate-y-0
              disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0
              transition-all duration-mars-fast ease-mars"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : null}
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        {/* Footer */}
        <div className="px-6 pb-6 text-center text-sm" style={{ color: 'var(--mars-color-text-secondary)' }}>
          Already have an account?{' '}
          <button
            onClick={() => { setError(null); onSwitchToLogin() }}
            className="font-medium underline underline-offset-2 transition-colors hover:opacity-80"
            style={{ color: 'var(--mars-color-primary-text)' }}
          >
            Sign in
          </button>
        </div>
      </div>
    </div>
  )
}
