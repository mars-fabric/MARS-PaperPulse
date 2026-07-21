'use client'

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react'
import { getApiUrl } from '@/lib/config'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'user'
  status: 'pending' | 'approved' | 'suspended'
}

interface AuthContextValue {
  user: User | null
  accessToken: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  isAdmin: () => boolean
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const LS_ACCESS  = 'mars_access_token'
const LS_REFRESH = 'mars_refresh_token'

async function fetchMe(token: string): Promise<User> {
  const res = await fetch(getApiUrl('/api/auth/me'), {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  })
  if (!res.ok) throw new Error(`/me returned ${res.status}`)
  return res.json()
}

async function fetchRefresh(refreshToken: string): Promise<{ access_token: string; refresh_token?: string }> {
  const res = await fetch(getApiUrl('/api/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) throw new Error(`/refresh returned ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]               = useState<User | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [isLoading, setIsLoading]     = useState(true)

  // ------------------------------------------------------------------
  // Bootstrap: restore session from localStorage on mount
  // ------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false

    async function restoreSession() {
      const storedToken   = localStorage.getItem(LS_ACCESS)
      const storedRefresh = localStorage.getItem(LS_REFRESH)

      if (!storedToken) {
        setIsLoading(false)
        return
      }

      try {
        // Try the stored access token first
        const me = await fetchMe(storedToken)
        if (cancelled) return
        setUser(me)
        setAccessToken(storedToken)
      } catch (err) {
        // Access token may be expired — attempt refresh
        if (!storedRefresh) {
          localStorage.removeItem(LS_ACCESS)
          setIsLoading(false)
          return
        }
        try {
          const data = await fetchRefresh(storedRefresh)
          if (cancelled) return
          localStorage.setItem(LS_ACCESS, data.access_token)
          if (data.refresh_token) localStorage.setItem(LS_REFRESH, data.refresh_token)

          const me = await fetchMe(data.access_token)
          if (cancelled) return
          setUser(me)
          setAccessToken(data.access_token)
        } catch {
          // Refresh also failed — clear everything
          if (!cancelled) {
            localStorage.removeItem(LS_ACCESS)
            localStorage.removeItem(LS_REFRESH)
          }
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    restoreSession()
    return () => { cancelled = true }
  }, [])

  // ------------------------------------------------------------------
  // login
  // ------------------------------------------------------------------
  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(getApiUrl('/api/auth/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })

    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body?.detail ?? `Login failed (${res.status})`)
    }

    const data: { access_token: string; refresh_token: string } = await res.json()
    localStorage.setItem(LS_ACCESS,  data.access_token)
    localStorage.setItem(LS_REFRESH, data.refresh_token)

    const me = await fetchMe(data.access_token)
    setUser(me)
    setAccessToken(data.access_token)
  }, [])

  // ------------------------------------------------------------------
  // logout
  // ------------------------------------------------------------------
  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(LS_REFRESH)
    const token        = localStorage.getItem(LS_ACCESS)

    try {
      if (refreshToken) {
        await fetch(getApiUrl('/api/auth/logout'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
      }
    } catch {
      // Best-effort — always clear locally even if server call fails
    } finally {
      localStorage.removeItem(LS_ACCESS)
      localStorage.removeItem(LS_REFRESH)
      setUser(null)
      setAccessToken(null)
    }
  }, [])

  // ------------------------------------------------------------------
  // isAdmin
  // ------------------------------------------------------------------
  const isAdmin = useCallback(() => user?.role === 'admin', [user])

  return (
    <AuthContext.Provider value={{ user, accessToken, isLoading, login, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
