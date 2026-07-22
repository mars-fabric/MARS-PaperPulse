'use client'

import React, { useState } from 'react'
import { FileText, Image, Code2, Database, Download, Eye, Folder, ChevronDown, RefreshCw } from 'lucide-react'

interface Artifact {
  id: string
  name: string
  type: 'code' | 'data' | 'document' | 'image' | 'other'
  size: number
  path: string
  timestamp?: string
  status?: 'pending' | 'completed' | 'failed'
}

interface ModernArtifactsViewerProps {
  artifacts?: Artifact[]
  title?: string
  onViewFile?: (path: string) => void
  onDownloadFile?: (path: string) => void
  onRefresh?: () => void
  isLoading?: boolean
}

const typeConfig: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  code: {
    icon: <Code2 className="w-4 h-4" />,
    color: '#8B5CF6',
    label: 'Code',
  },
  data: {
    icon: <Database className="w-4 h-4" />,
    color: '#06B6D4',
    label: 'Data',
  },
  document: {
    icon: <FileText className="w-4 h-4" />,
    color: '#3B82F6',
    label: 'Document',
  },
  image: {
    icon: <Image className="w-4 h-4" />,
    color: '#EC4899',
    label: 'Image',
  },
  other: {
    icon: <Folder className="w-4 h-4" />,
    color: '#6B7280',
    label: 'File',
  },
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

export default function ModernArtifactsViewer({
  artifacts = [],
  title = 'Generated Artifacts',
  onViewFile,
  onDownloadFile,
  onRefresh,
  isLoading = false,
}: ModernArtifactsViewerProps) {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    all: true,
  })

  // Group artifacts by type
  const groupedArtifacts = artifacts.reduce(
    (acc, artifact) => {
      const type = artifact.type || 'other'
      if (!acc[type]) acc[type] = []
      acc[type].push(artifact)
      return acc
    },
    {} as Record<string, Artifact[]>
  )

  const toggleGroup = (type: string) => {
    setExpandedGroups(prev => ({
      ...prev,
      [type]: !prev[type],
    }))
  }

  if (artifacts.length === 0) {
    return (
      <div
        className="rounded-lg border p-6 text-center"
        style={{
          backgroundColor: 'var(--mars-color-surface)',
          borderColor: 'var(--mars-color-border)',
        }}
      >
        <Folder className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--mars-color-text-tertiary)' }} />
        <p style={{ color: 'var(--mars-color-text-tertiary)' }}>No artifacts generated yet</p>
        <p style={{ color: 'var(--mars-color-text-disabled)', fontSize: '12px' }}>
          Files will appear here after execution
        </p>
      </div>
    )
  }

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3.5 border-b"
        style={{
          backgroundColor: 'var(--mars-color-surface-raised)',
          borderColor: 'var(--mars-color-border)',
        }}
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {title}
          </span>
          <span
            className="text-xs px-2 py-1 rounded-full"
            style={{
              backgroundColor: 'rgba(255,255,255,0.1)',
              color: 'var(--mars-color-text-tertiary)',
            }}
          >
            {artifacts.length} file{artifacts.length !== 1 ? 's' : ''}
          </span>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="p-1.5 rounded-lg transition-colors hover:bg-[var(--mars-color-surface-overlay)] disabled:opacity-50"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Groups */}
      <div className="divide-y" style={{ borderColor: 'var(--mars-color-border)' }}>
        {Object.entries(groupedArtifacts).map(([type, files]) => {
          const isExpanded = expandedGroups[type] !== false
          const config = typeConfig[type] || typeConfig.other

          return (
            <div key={type}>
              {/* Group Header */}
              <button
                onClick={() => toggleGroup(type)}
                className="w-full flex items-center justify-between px-5 py-3 hover:bg-[var(--mars-color-surface-overlay)] transition-colors"
                style={{
                  borderBottom: isExpanded ? '1px solid var(--mars-color-border)' : 'none',
                }}
              >
                <div className="flex items-center gap-3">
                  <div style={{ color: config.color }}>
                    {config.icon}
                  </div>
                  <span className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
                    {config.label} Files
                  </span>
                  <span
                    className="text-xs px-2 py-0.5 rounded"
                    style={{
                      backgroundColor: `${config.color}20`,
                      color: config.color,
                    }}
                  >
                    {files.length}
                  </span>
                </div>
                <ChevronDown
                  className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                  style={{ color: 'var(--mars-color-text-secondary)' }}
                />
              </button>

              {/* Group Items */}
              {isExpanded && (
                <div className="bg-[var(--mars-color-surface-overlay)] space-y-1 p-2">
                  {files.map((file) => (
                    <div
                      key={file.id}
                      className="flex items-center justify-between p-3 rounded-lg hover:bg-[var(--mars-color-surface-sunken)] transition-colors group"
                      style={{
                        backgroundColor: 'rgba(255,255,255,0.02)',
                      }}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div style={{ color: config.color }}>
                          {config.icon}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p
                            className="text-sm font-medium truncate"
                            style={{ color: 'var(--mars-color-text)' }}
                            title={file.name}
                          >
                            {file.name}
                          </p>
                          <p
                            className="text-xs"
                            style={{ color: 'var(--mars-color-text-tertiary)' }}
                          >
                            {formatBytes(file.size)}
                            {file.timestamp && ` · ${file.timestamp}`}
                          </p>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        {onViewFile && (
                          <button
                            onClick={() => onViewFile(file.path)}
                            className="p-1.5 rounded-lg transition-colors hover:bg-[var(--mars-color-surface)]"
                            style={{ color: 'var(--mars-color-text-secondary)' }}
                            title="Preview file"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        )}
                        {onDownloadFile && (
                          <button
                            onClick={() => onDownloadFile(file.path)}
                            className="p-1.5 rounded-lg transition-colors hover:bg-[var(--mars-color-surface)]"
                            style={{ color: 'var(--mars-color-text-secondary)' }}
                            title="Download file"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
