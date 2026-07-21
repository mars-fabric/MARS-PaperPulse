/**
 * api.ts — Authenticated fetch wrapper for MARS-PaperPulse
 *
 * Features:
 *  - Attaches Authorization: Bearer <token> from localStorage
 *  - Generates a W3C traceparent header for distributed tracing
 *  - On 401: attempts a single token refresh, retries the request,
 *    then calls logout() if refresh also fails
 */

import { getApiUrl } from '@/lib/config'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LS_ACCESS  = 'mars_access_token'
const LS_REFRESH = 'mars_refresh_token'

// ---------------------------------------------------------------------------
// Tracing helpers
// ---------------------------------------------------------------------------

/** Generate `n` cryptographically-random hex characters. */
function randomHex(bytes: number): string {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const arr = new Uint8Array(bytes)
    crypto.getRandomValues(arr)
    return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('')
  }
  // Node.js (SSR) fallback
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  return require('crypto').randomBytes(bytes).toString('hex')
}

/**
 * Generate a W3C traceparent header value.
 * Format: `00-<32 hex trace-id>-<16 hex parent-id>-01`
 */
export function generateTraceparent(): string {
  return `00-${randomHex(16)}-${randomHex(8)}-01`
}

// ---------------------------------------------------------------------------
// Token refresh
// ---------------------------------------------------------------------------

async function refreshTokens(): Promise<string> {
  const refreshToken = localStorage.getItem(LS_REFRESH)
  if (!refreshToken) throw new Error('No refresh token available')

  const res = await fetch(getApiUrl('/api/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  if (!res.ok) throw new Error(`Token refresh failed (${res.status})`)

  const data: { access_token: string; refresh_token?: string } = await res.json()
  localStorage.setItem(LS_ACCESS, data.access_token)
  if (data.refresh_token) localStorage.setItem(LS_REFRESH, data.refresh_token)
  return data.access_token
}

async function doLogout(): Promise<void> {
  try {
    const { useAuth } = await import('@/contexts/AuthContext')
    // Dynamic import — useAuth() is a hook and can't be called here directly.
    // Instead, dispatch a custom event that AuthContext listens to if needed,
    // or simply clear localStorage and reload.
  } catch {
    // no-op
  }
  localStorage.removeItem(LS_ACCESS)
  localStorage.removeItem(LS_REFRESH)
  // Hard-redirect to home so the app re-initialises in a logged-out state
  if (typeof window !== 'undefined') {
    window.location.href = '/'
  }
}

// ---------------------------------------------------------------------------
// Core fetch helper
// ---------------------------------------------------------------------------

interface ApiCallOptions extends RequestInit {
  /** Skip automatic 401 retry with refresh (used internally to avoid loops). */
  _skipRefresh?: boolean
}

/**
 * Perform an authenticated API call.
 *
 * @param path    API path (e.g. `/api/tasks`)
 * @param options Standard `RequestInit` plus optional `_skipRefresh` flag
 * @returns       Parsed response body as `T`
 */
export async function apiCall<T = unknown>(
  path: string,
  options: ApiCallOptions = {},
): Promise<T> {
  const { _skipRefresh = false, ...fetchOptions } = options

  const token = localStorage.getItem(LS_ACCESS)
  const traceparent = generateTraceparent()

  const headers = new Headers(fetchOptions.headers ?? {})
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  headers.set('traceparent', traceparent)

  const url = getApiUrl(path)

  let res = await fetch(url, { ...fetchOptions, headers })

  // ------------------------------------------------------------------
  // 401 handling: try refresh once, then retry
  // ------------------------------------------------------------------
  if (res.status === 401 && !_skipRefresh) {
    try {
      const newToken = await refreshTokens()

      headers.set('Authorization', `Bearer ${newToken}`)
      headers.set('traceparent', generateTraceparent())

      res = await fetch(url, { ...fetchOptions, headers })
    } catch {
      // Refresh failed — logout and propagate
      await doLogout()
      throw new Error('Session expired. Please log in again.')
    }

    if (res.status === 401) {
      await doLogout()
      throw new Error('Session expired. Please log in again.')
    }
  }

  // ------------------------------------------------------------------
  // Parse response
  // ------------------------------------------------------------------
  if (!res.ok) {
    let detail: string = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
      else if (typeof body?.message === 'string') detail = body.message
    } catch {
      // body was not JSON
    }
    throw new Error(`API error ${res.status}: ${detail}`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json() as Promise<T>
}
