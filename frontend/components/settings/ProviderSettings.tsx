'use client'

import React from 'react'
import { X } from 'lucide-react'
import { useProviders } from '@/hooks/useProviders'
import ProviderCard from './ProviderCard'

interface ProviderSettingsProps {
  onClose: () => void
}

export default function ProviderSettings({ onClose }: ProviderSettingsProps) {
  const {
    providers,
    configuredProviders,
    availableModels,
    isLoading,
    testProvider,
    saveCredentials,
    removeCredentials,
  } = useProviders()

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-3xl max-h-[85vh] rounded-2xl border shadow-2xl overflow-hidden flex flex-col"
        style={{
          backgroundColor: 'var(--mars-color-bg)',
          borderColor: 'var(--mars-color-border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          <div>
            <h2
              className="text-base font-bold"
              style={{ color: 'var(--mars-color-text)' }}
            >
              LLM Provider Settings
            </h2>
            <p
              className="text-xs mt-0.5"
              style={{ color: 'var(--mars-color-text-tertiary)' }}
            >
              {configuredProviders.length > 0
                ? `${configuredProviders.length} active provider${configuredProviders.length !== 1 ? 's' : ''} · ${availableModels.length} models available`
                : 'Configure at least one LLM provider to get started'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors hover:bg-[var(--mars-color-bg-hover)]"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div
                className="animate-spin rounded-full h-6 w-6 border-2 border-t-transparent"
                style={{ borderColor: 'var(--mars-color-border)', borderTopColor: 'transparent' }}
              />
              <span
                className="ml-3 text-sm"
                style={{ color: 'var(--mars-color-text-secondary)' }}
              >
                Loading providers...
              </span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {providers.map((provider) => (
                <ProviderCard
                  key={provider.provider_id}
                  provider={provider}
                  onTest={testProvider}
                  onSave={saveCredentials}
                  onRemove={removeCredentials}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {configuredProviders.length === 0 && !isLoading && (
          <div
            className="px-6 py-3 border-t text-center"
            style={{ borderColor: 'var(--mars-color-border)' }}
          >
            <p
              className="text-xs"
              style={{ color: 'var(--mars-color-text-tertiary)' }}
            >
              Click <strong>Configure</strong> on any provider above to add your
              API credentials. Existing <code>.env</code> credentials are
              detected automatically.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
