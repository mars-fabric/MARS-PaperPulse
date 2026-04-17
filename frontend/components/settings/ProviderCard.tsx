'use client'

import React, { useState } from 'react'
import type { Provider, ProviderTestResult } from '@/types/providers'
import ProviderStatusBadge from './ProviderStatusBadge'
import ProviderCredentialForm from './ProviderCredentialForm'

interface ProviderCardProps {
  provider: Provider
  onTest: (
    providerId: string,
    creds: Record<string, string>
  ) => Promise<ProviderTestResult>
  onSave: (
    providerId: string,
    creds: Record<string, string>
  ) => Promise<{ status: string; message: string }>
  onRemove: (providerId: string) => Promise<void>
}

/** Icon for each provider (simple colored circle with letter) */
function ProviderIcon({ name }: { name: string }) {
  const colors: Record<string, string> = {
    OpenAI: '#10a37f',
    'Azure OpenAI': '#0078d4',
    Anthropic: '#d4a574',
    'Google Gemini': '#4285f4',
    'Mistral AI': '#ff7000',
    'AWS Bedrock': '#ff9900',
  }
  const color = colors[name] ?? '#8b5cf6'
  const letter = name.charAt(0)

  return (
    <div
      className="w-9 h-9 rounded-lg flex items-center justify-center text-white text-sm font-bold"
      style={{ backgroundColor: color }}
    >
      {letter}
    </div>
  )
}

export default function ProviderCard({
  provider,
  onTest,
  onSave,
  onRemove,
}: ProviderCardProps) {
  const [editing, setEditing] = useState(false)
  const [removing, setRemoving] = useState(false)

  const isConfigured = provider.status !== 'not_configured'

  const handleRemove = async () => {
    setRemoving(true)
    try {
      await onRemove(provider.provider_id)
    } finally {
      setRemoving(false)
    }
  }

  if (editing) {
    return (
      <ProviderCredentialForm
        providerName={provider.display_name}
        providerId={provider.provider_id}
        fields={provider.credential_fields}
        onTest={(creds) => onTest(provider.provider_id, creds)}
        onSave={async (creds) => {
          const result = await onSave(provider.provider_id, creds)
          setEditing(false)
          return result
        }}
        onCancel={() => setEditing(false)}
      />
    )
  }

  return (
    <div
      className="rounded-xl border p-4 transition-colors hover:border-[var(--mars-color-border-hover)]"
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
      }}
    >
      <div className="flex items-start gap-3">
        <ProviderIcon name={provider.display_name} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--mars-color-text)' }}
            >
              {provider.display_name}
            </h3>
            <ProviderStatusBadge status={provider.status} />
          </div>

          {isConfigured && (
            <div className="space-y-0.5">
              {/* Show masked credential values */}
              {provider.credential_fields
                .filter((f) => f.has_value)
                .slice(0, 2)
                .map((f) => (
                  <p
                    key={f.name}
                    className="text-[10px] font-mono truncate"
                    style={{ color: 'var(--mars-color-text-tertiary)' }}
                  >
                    {f.display_name}: {f.masked_value || '****'}
                  </p>
                ))}
              <p
                className="text-[10px]"
                style={{ color: 'var(--mars-color-text-secondary)' }}
              >
                {provider.models.length} model
                {provider.models.length !== 1 ? 's' : ''} available
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-3">
        {isConfigured ? (
          <>
            <button
              onClick={() => setEditing(true)}
              className="px-2.5 py-1 rounded text-[11px] font-medium border transition-colors
                hover:bg-[var(--mars-color-bg-hover)]"
              style={{
                borderColor: 'var(--mars-color-border)',
                color: 'var(--mars-color-text-secondary)',
              }}
            >
              Edit
            </button>
            <button
              onClick={handleRemove}
              disabled={removing}
              className="px-2.5 py-1 rounded text-[11px] font-medium border transition-colors
                hover:bg-red-500/10 hover:border-red-500/30 hover:text-red-500
                disabled:opacity-40"
              style={{
                borderColor: 'var(--mars-color-border)',
                color: 'var(--mars-color-text-tertiary)',
              }}
            >
              {removing ? 'Removing...' : 'Remove'}
            </button>
          </>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="px-3 py-1.5 rounded-lg text-[11px] font-semibold text-white transition-all
              hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
            style={{
              background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            }}
          >
            Configure
          </button>
        )}
      </div>
    </div>
  )
}
