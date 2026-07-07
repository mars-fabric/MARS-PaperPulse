'use client'

import React, { useState, useEffect } from 'react'
import { RefreshCw, Download, FileText, Image, File } from 'lucide-react'
import { getApiUrl } from '@/lib/config'

interface StageArtifactsPanelProps {
  title: string
  files: string[]
  onRefresh: () => void
  taskId: string | null
}

type FileCategory = 'Results' | 'Code' | 'Data' | 'Chats' | 'Plan'

const CODE_EXTENSIONS = new Set(['.py', '.ipynb', '.r', '.sh', '.m', '.jl', '.R'])
const DATA_EXTENSIONS = new Set(['.csv', '.json', '.npy', '.pkl', '.npz', '.h5', '.parquet', '.dat', '.fits', '.xlsx'])
const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'])
const PDF_TEX_EXTENSIONS = new Set(['.pdf', '.tex'])

function getExtension(filePath: string): string {
  const name = filePath.split('/').pop() || filePath
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

function getBasename(filePath: string): string {
  return (filePath.split('/').pop() || filePath).toLowerCase()
}

function categorizeFile(filePath: string): FileCategory {
  const basename = getBasename(filePath)
  const ext = getExtension(filePath)

  // Priority 1: Plan
  if (basename.includes('plan')) return 'Plan'

  // Priority 2: Chats
  if (
    basename.includes('chat') ||
    basename.includes('conversation') ||
    basename.includes('dialogue') ||
    ext === '.jsonl'
  ) return 'Chats'

  // Priority 3: Code
  if (CODE_EXTENSIONS.has(ext)) return 'Code'

  // Priority 4: Data
  if (DATA_EXTENSIONS.has(ext)) return 'Data'

  // Priority 5: Results (everything else)
  return 'Results'
}

function getFileIcon(filePath: string) {
  const ext = getExtension(filePath)
  if (PDF_TEX_EXTENSIONS.has(ext)) return <FileText className="w-4 h-4" />
  if (IMAGE_EXTENSIONS.has(ext)) return <Image className="w-4 h-4" />
  return <File className="w-4 h-4" />
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const CATEGORY_ORDER: FileCategory[] = ['Results', 'Code', 'Data', 'Chats', 'Plan']

export default function StageArtifactsPanel({
  title,
  files,
  onRefresh,
  taskId: _taskId,
}: StageArtifactsPanelProps) {
  const [activeTab, setActiveTab] = useState<FileCategory>('Results')
  const [fileSizes, setFileSizes] = useState<Record<string, number>>({})

  // Categorize all files
  const categorized: Record<FileCategory, string[]> = {
    Results: [],
    Code: [],
    Data: [],
    Chats: [],
    Plan: [],
  }
  for (const f of files) {
    categorized[categorizeFile(f)].push(f)
  }

  // Available tabs (only categories with files)
  const availableTabs = CATEGORY_ORDER.filter(cat => categorized[cat].length > 0)

  // Auto-select first available tab if current tab has no files
  useEffect(() => {
    if (availableTabs.length > 0 && !availableTabs.includes(activeTab)) {
      setActiveTab(availableTabs[0])
    }
  }, [availableTabs, activeTab])

  // Fetch file sizes
  useEffect(() => {
    if (files.length === 0) return
    const fetchSizes = async () => {
      const newSizes: Record<string, number> = {}
      await Promise.all(
        files.map(async (path) => {
          try {
            const res = await fetch(
              getApiUrl(`/api/files/info?path=${encodeURIComponent(path)}`)
            )
            if (res.ok) {
              const data = await res.json()
              if (typeof data.size === 'number') newSizes[path] = data.size
            }
          } catch {
            // ignore
          }
        })
      )
      setFileSizes(prev => ({ ...prev, ...newSizes }))
    }
    fetchSizes()
  }, [files])

  const totalSize = Object.values(fileSizes).reduce((a, b) => a + b, 0)
  const currentFiles = categorized[activeTab] ?? []

  const getFileName = (path: string) => path.split('/').pop() || path

  const handleDownloadAll = () => {
    currentFiles.forEach((path, i) => {
      setTimeout(() => {
        const url = getApiUrl(`/api/files/download?path=${encodeURIComponent(path)}`)
        window.open(url, '_blank')
      }, i * 100)
    })
  }

  if (files.length === 0) return null

  return (
    <div
      className="rounded-mars-md border overflow-hidden"
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
          {title}
        </span>
        <div className="flex items-center gap-3">
          <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            {files.length} file{files.length !== 1 ? 's' : ''}
            {totalSize > 0 && ` · ${formatBytes(totalSize)}`}
          </span>
          <button
            onClick={onRefresh}
            title="Refresh"
            className="p-1 rounded transition-colors"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleDownloadAll}
            title="Download all files in current tab"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-mars-sm text-xs font-medium border transition-colors"
            style={{
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text-secondary)',
            }}
          >
            <Download className="w-3 h-3" />
            Download all
          </button>
        </div>
      </div>

      {/* Tabs */}
      {availableTabs.length > 1 && (
        <div
          className="flex border-b"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          {availableTabs.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveTab(cat)}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium transition-colors"
              style={{
                color: activeTab === cat ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
                borderBottom: activeTab === cat ? '2px solid var(--mars-color-accent)' : '2px solid transparent',
              }}
            >
              {cat}
              <span
                className="inline-flex items-center justify-center rounded-full text-xs px-1.5 py-0.5 min-w-[20px]"
                style={{
                  backgroundColor: activeTab === cat
                    ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.15))'
                    : 'var(--mars-color-surface-overlay)',
                  color: activeTab === cat ? 'var(--mars-color-accent)' : 'var(--mars-color-text-tertiary)',
                }}
              >
                {categorized[cat].length}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* File list */}
      <div className="divide-y" style={{ borderColor: 'var(--mars-color-border)' }}>
        {currentFiles.length === 0 ? (
          <p className="px-4 py-3 text-sm" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            No files in this category.
          </p>
        ) : (
          currentFiles.map(path => {
            const fileName = getFileName(path)
            const size = fileSizes[path]
            const downloadUrl = getApiUrl(`/api/files/download?path=${encodeURIComponent(path)}`)
            return (
              <div
                key={path}
                className="flex items-center gap-3 px-4 py-2.5"
                style={{ borderColor: 'var(--mars-color-border)' }}
              >
                <span style={{ color: 'var(--mars-color-text-tertiary)', flexShrink: 0 }}>
                  {getFileIcon(path)}
                </span>
                <span
                  className="flex-1 text-sm truncate"
                  style={{ color: 'var(--mars-color-text)' }}
                  title={fileName}
                >
                  {fileName}
                </span>
                {size !== undefined && (
                  <span className="text-xs shrink-0" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                    {formatBytes(size)}
                  </span>
                )}
                <a
                  href={downloadUrl}
                  download={fileName}
                  className="flex items-center gap-1 text-xs font-medium shrink-0 ml-1"
                  style={{ color: 'var(--mars-color-primary)' }}
                >
                  <Download className="w-3.5 h-3.5" />
                  Download
                </a>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
