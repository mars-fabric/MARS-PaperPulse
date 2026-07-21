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
        className="relative w-full max-w-md rounded-xl shadow-2xl bg-gray-900 border border-gray-700/60 flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-0">
          <div>
            <h2 id="login-title" className="text-xl font-semibold text-white">
              Sign in
            </h2>
            <p className="mt-0.5 text-sm text-gray-400">Welcome back to MARS PaperPulse</p>
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
          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-email" className="text-sm font-medium text-gray-300">
              Email address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <input
                ref={emailRef}
                id="login-email"
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
            <label htmlFor="login-password" className="text-sm font-medium text-gray-300">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700
                  text-white placeholder-gray-500 text-sm
                  focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent
                  transition-colors"
              />
            </div>
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
            disabled={loading || !email.trim() || !password}
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg
              text-sm font-semibold text-white
              bg-gradient-to-r from-violet-600 to-indigo-600
              hover:from-violet-500 hover:to-indigo-500
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-150 shadow-lg shadow-violet-900/30"
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
        <div className="px-6 pb-6 text-center text-sm text-gray-400">
          Don&apos;t have an account?{' '}
          <button
            onClick={() => { setError(null); onSwitchToSignup() }}
            className="text-violet-400 hover:text-violet-300 font-medium underline underline-offset-2 transition-colors"
          >
            Sign up
          </button>
        </div>
      </div>
    </div>
  )
}
