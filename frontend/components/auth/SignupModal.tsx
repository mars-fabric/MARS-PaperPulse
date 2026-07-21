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
        className="relative w-full max-w-md rounded-xl shadow-2xl bg-gray-900 border border-gray-700/60 flex flex-col max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-0 sticky top-0 bg-gray-900 z-10">
          <div>
            <h2 id="signup-title" className="text-xl font-semibold text-white">
              Create account
            </h2>
            <p className="mt-0.5 text-sm text-gray-400">Join MARS PaperPulse</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate className="px-6 py-6 flex flex-col gap-4">
          {/* Full name (optional) */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-name" className="text-sm font-medium text-gray-300">
              Full name <span className="text-gray-500 font-normal">(optional)</span>
            </label>
            <div className="relative">
              <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <input
                ref={nameRef}
                id="signup-name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Jane Smith"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700
                  text-white placeholder-gray-500 text-sm
                  focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent
                  transition-colors"
              />
            </div>
          </div>

          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-email" className="text-sm font-medium text-gray-300">
              Email address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <input
                id="signup-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700
                  text-white placeholder-gray-500 text-sm
                  focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent
                  transition-colors"
              />
            </div>
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-password" className="text-sm font-medium text-gray-300">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <input
                id="signup-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={e => { setPassword(e.target.value); setShowPolicy(true) }}
                onFocus={() => setShowPolicy(true)}
                placeholder="••••••••"
                required
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700
                  text-white placeholder-gray-500 text-sm
                  focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent
                  transition-colors"
              />
            </div>

            {/* Strength bar */}
            {password && strength && (
              <div className="flex flex-col gap-1.5 mt-1">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${strength.color}`}
                      style={{ width: `${(strength.passed / POLICY.length) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-400 shrink-0 w-20 text-right">{strength.label}</span>
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
                            : <XCircle      className="w-3.5 h-3.5 text-gray-600 shrink-0" />
                          }
                          <span className={ok ? 'text-gray-300' : 'text-gray-500'}>
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
            <label htmlFor="signup-confirm" className="text-sm font-medium text-gray-300">
              Confirm password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <input
                id="signup-confirm"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                className={`w-full pl-10 pr-4 py-2.5 rounded-lg bg-gray-800 border text-white
                  placeholder-gray-500 text-sm
                  focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent
                  transition-colors
                  ${confirmPassword && !passwordsMatch ? 'border-red-600' : 'border-gray-700'}`}
              />
            </div>
            {confirmPassword && !passwordsMatch && (
              <p className="text-xs text-red-400">Passwords do not match.</p>
            )}
          </div>

          {/* Error banner */}
          {error && (
            <div className="flex items-start gap-2.5 px-4 py-3 rounded-lg bg-red-950/60 border border-red-700/50 text-red-300 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !email.trim() || !password || !confirmPassword}
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg
              text-sm font-semibold text-white
              bg-gradient-to-r from-violet-600 to-indigo-600
              hover:from-violet-500 hover:to-indigo-500
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-150 shadow-lg shadow-violet-900/30"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : null}
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        {/* Footer */}
        <div className="px-6 pb-6 text-center text-sm text-gray-400">
          Already have an account?{' '}
          <button
            onClick={() => { setError(null); onSwitchToLogin() }}
            className="text-violet-400 hover:text-violet-300 font-medium underline underline-offset-2 transition-colors"
          >
            Sign in
          </button>
        </div>
      </div>
    </div>
  )
}
