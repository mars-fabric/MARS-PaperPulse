import { NextRequest } from 'next/server'
import { config } from '@/lib/config'

// The Next.js dev rewrite proxy corrupts multipart request bodies larger than
// ~10MB (backend receives a truncated body, hangs, then 400s -> proxy 500s).
// This route handler intercepts /api/files/upload BEFORE the afterFiles rewrite
// and forwards the raw body straight to the backend from the server side, which
// has no such limit. The browser still uploads same-origin to :3000.
export const runtime = 'nodejs'
export const maxDuration = 300

export async function POST(request: NextRequest): Promise<Response> {
  const backend = config.apiUrl.replace(/\/$/, '')
  const url = `${backend}/api/files/upload`

  const headers: Record<string, string> = {}
  const contentType = request.headers.get('content-type')
  const auth = request.headers.get('authorization')
  const traceparent = request.headers.get('traceparent')
  if (contentType) headers['content-type'] = contentType
  if (auth) headers['authorization'] = auth
  if (traceparent) headers['traceparent'] = traceparent

  let upstream: Response
  try {
    upstream = await fetch(url, {
      method: 'POST',
      headers,
      body: request.body,
      // @ts-expect-error - duplex is required by undici when streaming a body
      duplex: 'half',
    })
  } catch (err) {
    return Response.json(
      { detail: `Upload proxy failed: ${err instanceof Error ? err.message : 'unknown error'}` },
      { status: 502 },
    )
  }

  const body = await upstream.arrayBuffer()
  return new Response(body, {
    status: upstream.status,
    headers: { 'content-type': upstream.headers.get('content-type') || 'application/json' },
  })
}
