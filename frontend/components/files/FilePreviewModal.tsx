'use client'

import React, { useState, useEffect } from 'react'
import { X, Download, Loader } from 'lucide-react'
import FilePreview from './FilePreview'
import { getApiUrl } from '@/lib/config'

interface FilePreviewModalProps {
  isOpen: boolean
  filePath: string | null
  fileName?: string
  onClose: () => void
}

export default function FilePreviewModal({
  isOpen,
  filePath,
  fileName,
  onClose,
}: FilePreviewModalProps) {
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch file content when filePath changes
  useEffect(() => {
    if (!isOpen || !filePath) {
      setFileContent(null)
      setError(null)
      return
    }

    const fetchFileContent = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await fetch(
          getApiUrl(`/api/files/content?path=${encodeURIComponent(filePath)}`)
        )
        if (!response.ok) {
          throw new Error(`Failed to fetch file: ${response.statusText}`)
        }
        const data = await response.json()
        setFileContent(data.content || null)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load file'
        setError(message)
        setFileContent(null)
      } finally {
        setIsLoading(false)
      }
    }

    fetchFileContent()
  }, [isOpen, filePath])

  if (!isOpen || !filePath) return null

  const downloadUrl = getApiUrl(`/api/files/download?path=${encodeURIComponent(filePath)}`)
  const displayName = fileName || filePath.split('/').pop() || filePath

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}
      onClick={onClose}
    >
      <div
        className="rounded-xl shadow-2xl flex flex-col max-h-[90vh] w-full max-w-5xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: 'var(--mars-color-surface)',
          borderColor: 'var(--mars-color-border)',
          border: '1px solid var(--mars-color-border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b shrink-0"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          <div className="flex-1 min-w-0">
            <h2
              className="text-lg font-semibold truncate"
              style={{ color: 'var(--mars-color-text)' }}
              title={displayName}
            >
              {displayName}
            </h2>
          </div>
          <div className="flex items-center gap-2 ml-4 shrink-0">
            <a
              href={downloadUrl}
              download={displayName}
              className="p-2 rounded-lg transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              title="Download file"
            >
              <Download className="w-4 h-4" />
            </a>
            <button
              onClick={onClose}
              className="p-2 rounded-lg transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Loader className="w-8 h-8 animate-spin mx-auto mb-3" style={{ color: 'var(--mars-color-primary)' }} />
                <p style={{ color: 'var(--mars-color-text-secondary)' }}>Loading file...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full p-6">
              <div className="text-center">
                <div
                  className="text-lg font-semibold mb-2"
                  style={{ color: 'var(--mars-color-danger)' }}
                >
                  Error loading file
                </div>
                <p style={{ color: 'var(--mars-color-text-secondary)' }}>
                  {error}
                </p>
                <a
                  href={downloadUrl}
                  download={displayName}
                  className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-lg text-sm font-medium text-white"
                  style={{ backgroundColor: 'var(--mars-color-primary)' }}
                >
                  <Download className="w-4 h-4" />
                  Download instead
                </a>
              </div>
            </div>
          ) : (
            <div className="p-6">
              <FilePreview
                filePath={filePath}
                fileName={displayName}
                content={fileContent}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
