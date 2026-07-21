import { getApiUrl } from './config'
import { generateTraceparent } from './api'

const LS_ACCESS = 'mars_access_token'
const LS_REFRESH = 'mars_refresh_token'

async function refreshAccessToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null
  const refreshToken = localStorage.getItem(LS_REFRESH)
  if (!refreshToken) return null
  try {
    const res = await fetch(getApiUrl('/api/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return null
    const data: { access_token: string; refresh_token?: string } = await res.json()
    localStorage.setItem(LS_ACCESS, data.access_token)
    if (data.refresh_token) localStorage.setItem(LS_REFRESH, data.refresh_token)
    return data.access_token
  } catch {
    return null
  }
}

function buildInit(options: RequestInit | undefined, token: string | null): RequestInit {
  const headers = new Headers(options?.headers ?? {})
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  headers.set('traceparent', generateTraceparent())
  return { ...options, headers }
}

/**
 * Fetch wrapper with automatic retry for transient network errors
 * (e.g. ECONNRESET / socket hang up through the Next.js proxy).
 *
 * Also attaches the `Authorization: Bearer <token>` header from localStorage
 * and a W3C `traceparent`, and transparently refreshes the access token once
 * on a 401 response before retrying.
 *
 * Only retries on *network* failures (TypeError from fetch); other HTTP error
 * responses are returned as-is for the caller to handle.
 */
export async function apiFetchWithRetry(
  path: string,
  options?: RequestInit,
  retries = 1,
): Promise<Response> {
  const url = getApiUrl(path)
  const token = typeof window !== 'undefined' ? localStorage.getItem(LS_ACCESS) : null

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, buildInit(options, token))

      // Transparently refresh the access token once on 401 and retry.
      if (res.status === 401) {
        const newToken = await refreshAccessToken()
        if (newToken) {
          return await fetch(url, buildInit(options, newToken))
        }
      }
      return res
    } catch (err) {
      // Only retry on network-level errors (ECONNRESET surfaces as TypeError)
      if (attempt < retries && err instanceof TypeError) {
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)))
        continue
      }
      throw err
    }
  }
  // Unreachable, but satisfies TS
  throw new Error('Fetch failed after retries')
}
