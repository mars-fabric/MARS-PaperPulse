'use client'

/**
 * useProviders — manages LLM provider state: list, configure, test, remove.
 *
 * Returns:
 *   providers          — all registered providers with status + credential schema
 *   configuredProviders — only those with credentials (status != 'not_configured')
 *   availableModels    — models from configured providers (for UI dropdowns)
 *   activeProvider     — the primary active provider ID
 *   isLoading          — true on first fetch
 *   testProvider()     — test credentials without storing
 *   saveCredentials()  — store credentials (vault + registry sync)
 *   removeCredentials() — remove stored credentials
 *   refreshProviders() — force refresh from backend
 */

import { useState, useEffect, useCallback } from 'react'
import type {
  Provider,
  ProviderTestResult,
  ProvidersListResponse,
} from '@/types/providers'
import { invalidateModelConfigCache } from '@/hooks/useModelConfig'

// Module-level cache for the provider list
let _providersCache: ProvidersListResponse | null = null

export function useProviders() {
  const [data, setData] = useState<ProvidersListResponse | null>(_providersCache)
  const [isLoading, setIsLoading] = useState(_providersCache === null)

  const fetchProviders = useCallback(async () => {
    try {
      const resp = await fetch('/api/providers')
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json: ProvidersListResponse = await resp.json()
      _providersCache = json
      setData(json)
    } catch (err) {
      console.error('Failed to fetch providers:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (_providersCache) {
      setData(_providersCache)
      setIsLoading(false)
      return
    }
    fetchProviders()
  }, [fetchProviders])

  const testProvider = useCallback(
    async (
      providerId: string,
      credentials: Record<string, string>
    ): Promise<ProviderTestResult> => {
      const resp = await fetch(`/api/providers/${providerId}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credentials }),
      })
      if (!resp.ok) {
        const text = await resp.text()
        return { success: false, message: `HTTP ${resp.status}: ${text}` }
      }
      return resp.json()
    },
    []
  )

  const saveCredentials = useCallback(
    async (
      providerId: string,
      credentials: Record<string, string>
    ): Promise<{ status: string; message: string }> => {
      const resp = await fetch(`/api/providers/${providerId}/credentials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credentials }),
      })
      const json = await resp.json()
      // Invalidate both provider and model caches, then refresh
      _providersCache = null
      invalidateModelConfigCache()
      await fetchProviders()
      return json
    },
    [fetchProviders]
  )

  const removeCredentials = useCallback(
    async (providerId: string): Promise<void> => {
      await fetch(`/api/providers/${providerId}/credentials`, {
        method: 'DELETE',
      })
      _providersCache = null
      invalidateModelConfigCache()
      await fetchProviders()
    },
    [fetchProviders]
  )

  const refreshProviders = useCallback(async () => {
    _providersCache = null
    setIsLoading(true)
    await fetchProviders()
  }, [fetchProviders])

  const providers: Provider[] = data?.providers ?? []
  const configuredProviders = providers.filter(
    (p) => p.status !== 'not_configured'
  )

  // Build available models from configured providers
  const availableModels = configuredProviders.flatMap((p) =>
    p.models.map((m) => ({
      value: m.model_id,
      label: m.display_name,
      provider: p.provider_id,
    }))
  )

  // Deduplicate by model_id (Azure and OpenAI share model names)
  const seen = new Set<string>()
  const dedupedModels = availableModels.filter((m) => {
    if (seen.has(m.value)) return false
    seen.add(m.value)
    return true
  })

  return {
    providers,
    configuredProviders,
    availableModels: dedupedModels,
    activeProvider: data?.active_provider ?? null,
    isLoading,
    testProvider,
    saveCredentials,
    removeCredentials,
    refreshProviders,
  }
}
