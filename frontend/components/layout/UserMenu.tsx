'use client'

import React, { useState, useRef, useEffect } from 'react'
import { LogOut, ShieldCheck, ChevronDown, Loader2 } from 'lucide-react'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getInitials(fullName: string, email: string): string {
  if (fullName && fullName.trim()) {
    const parts = fullName.trim().split(/\s+/)
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return fullName.trim().slice(0, 2).toUpperCase()
  }
  // Fall back to email
  return email.slice(0, 2).toUpperCase()
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RoleBadge({ role }: { role: 'admin' | 'user' }) {
  if (role === 'admin') {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold
        bg-amber-500/15 text-amber-400 border border-amber-500/25">
        <ShieldCheck className="w-2.5 h-2.5" />
        Admin
      </span>
    )
  }
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium
      bg-gray-700/60 text-gray-400 border border-gray-600/30">
      User
    </span>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function UserMenu() {
  const { user, logout, isAdmin } = useAuth()
  const [open, setOpen]           = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open])

  if (!user) return null

  const initials    = getInitials(user.full_name, user.email)
  const displayName = user.full_name?.trim() || user.email

  const handleLogout = async () => {
    setOpen(false)
    setLoggingOut(true)
    try {
      await logout()
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <div ref={menuRef} className="relative flex-shrink-0">
      {/* Trigger button */}
      <button
        onClick={() => setOpen(v => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg
          text-gray-300 hover:text-white hover:bg-gray-800/60
          transition-colors duration-150"
      >
        {/* Avatar */}
        <span
          className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white select-none"
          style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
          aria-hidden="true"
        >
          {initials}
        </span>

        <ChevronDown
          className={`w-3.5 h-3.5 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown */}
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1.5 w-56 rounded-xl shadow-2xl
            bg-gray-900 border border-gray-700/70 py-1.5 z-50
            animate-[mars-fade-in_0.1s_ease-out]"
        >
          {/* User info header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-700/50">
            <span
              className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white shrink-0"
              style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
            >
              {initials}
            </span>
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-sm font-semibold text-white truncate" title={displayName}>
                {displayName}
              </span>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400 truncate max-w-[110px]" title={user.email}>
                  {user.email}
                </span>
                <RoleBadge role={user.role} />
              </div>
            </div>
          </div>

          {/* Admin panel link */}
          {isAdmin() && (
            <Link
              href="/admin"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-300
                hover:text-white hover:bg-gray-800/70 transition-colors"
            >
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              Admin Panel
            </Link>
          )}

          {/* Divider before logout */}
          <div className="my-1 border-t border-gray-700/50" />

          {/* Logout */}
          <button
            role="menuitem"
            onClick={handleLogout}
            disabled={loggingOut}
            className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-300
              hover:text-red-400 hover:bg-red-500/10 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loggingOut ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogOut className="w-4 h-4" />
            )}
            {loggingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      )}
    </div>
  )
}
