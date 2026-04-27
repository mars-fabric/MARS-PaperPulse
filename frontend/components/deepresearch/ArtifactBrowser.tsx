'use client'

import React, { useEffect, useMemo, useState, useCallback } from 'react'
import {
  Download, RefreshCw, Image as ImageIcon, Code2, Database,
  FileText, MessageSquare, ListChecks, Eye, Loader2,
} from 'lucide-react'
import { Button, Tabs, Modal, type TabItem } from '@/components/core'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import { getApiUrl } from '@/lib/config'
import {
  ARTIFACT_CATEGORY_LABELS,
  ARTIFACT_CATEGORY_ORDER,
  type ArtifactCategory,
  type ArtifactItem,
  type ArtifactManifest,
} from '@/types/deepresearch'

interface ArtifactBrowserProps {
  taskId: string
  stageNum: number
  manifest: ArtifactManifest | null
  totalFiles: number
  totalBytes: number
  onRefresh: () => Promise<unknown>
}

const CATEGORY_ICONS: Record<ArtifactCategory, React.ReactNode> = {
  results:  <FileText  className="w-3.5 h-3.5" />,
  plots:    <ImageIcon className="w-3.5 h-3.5" />,
  code:     <Code2     className="w-3.5 h-3.5" />,
  data:     <Database  className="w-3.5 h-3.5" />,
  reports:  <FileText  className="w-3.5 h-3.5" />,
  chats:    <MessageSquare className="w-3.5 h-3.5" />,
  planning: <ListChecks className="w-3.5 h-3.5" />,
}

// Extensions that we render inline as text/markdown without a backend round-trip
// being expensive. Anything bigger than this is download-only by default.
const INLINE_PREVIEW_MAX_BYTES = 5 * 1024 * 1024

function formatBytes(n: number): string {
  if (!n) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let v = n, i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`
}

function isImage(item: ArtifactItem): boolean {
  return item.mime.startsWith('image/') || /\.(png|jpe?g|gif|svg|webp)$/i.test(item.name)
}

function downloadUrl(path: string): string {
  return getApiUrl(`/api/files/download?path=${encodeURIComponent(path)}`)
}

function serveUrl(path: string): string {
  // /serve-image works for any image; /serve handles other inline-viewable types
  return getApiUrl(`/api/files/serve?path=${encodeURIComponent(path)}`)
}

function imageUrl(path: string): string {
  return getApiUrl(`/api/files/serve-image?path=${encodeURIComponent(path)}`)
}

export default function ArtifactBrowser({
  taskId,
  stageNum,
  manifest,
  totalFiles,
  totalBytes,
  onRefresh,
}: ArtifactBrowserProps) {
  const availableCategories = useMemo<ArtifactCategory[]>(() => {
    if (!manifest) return []
    return ARTIFACT_CATEGORY_ORDER.filter(c => (manifest[c]?.length ?? 0) > 0)
  }, [manifest])

  const [activeCat, setActiveCat] = useState<ArtifactCategory | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [previewing, setPreviewing] = useState<ArtifactItem | null>(null)

  // Auto-pick the first non-empty category whenever the manifest changes
  useEffect(() => {
    if (availableCategories.length === 0) {
      setActiveCat(null)
    } else if (!activeCat || !availableCategories.includes(activeCat)) {
      setActiveCat(availableCategories[0])
    }
  }, [availableCategories, activeCat])

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try { await onRefresh() } finally { setRefreshing(false) }
  }, [onRefresh])

  const handleDownloadAll = useCallback(() => {
    // Stream the zip via a hidden anchor — keeps it as a normal browser download
    const a = document.createElement('a')
    a.href = getApiUrl(`/api/deepresearch/${taskId}/stages/${stageNum}/artifacts/zip`)
    a.rel = 'noopener'
    a.click()
  }, [taskId, stageNum])

  const tabs = useMemo<TabItem[]>(() =>
    availableCategories.map(cat => ({
      id: cat,
      label: ARTIFACT_CATEGORY_LABELS[cat],
      icon: CATEGORY_ICONS[cat],
      badge: manifest?.[cat]?.length ?? 0,
    })),
  [availableCategories, manifest])

  const items = activeCat ? (manifest?.[activeCat] ?? []) : []

  // Empty state — manifest yet to be computed or genuinely empty
  if (!manifest || availableCategories.length === 0) {
    return (
      <div
        className="rounded-mars-md border p-4 flex flex-col gap-3"
        style={{
          borderColor: 'var(--mars-color-border)',
          backgroundColor: 'var(--mars-color-surface)',
        }}
      >
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            Stage 3 artifacts
          </span>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            title="Re-scan work directory"
            className="p-1.5 rounded-mars-sm transition-colors disabled:opacity-50"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            {refreshing
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <RefreshCw className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
          No artifacts found yet. Click refresh once the experiment finishes writing files.
        </p>
      </div>
    )
  }

  return (
    <div
      className="rounded-mars-md border flex flex-col overflow-hidden"
      style={{
        borderColor: 'var(--mars-color-border)',
        backgroundColor: 'var(--mars-color-surface)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b flex-shrink-0"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
            Artifacts
          </span>
          <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            {totalFiles} {totalFiles === 1 ? 'file' : 'files'} · {formatBytes(totalBytes)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            title="Re-scan work directory"
            className="flex items-center gap-1 px-2 py-1 text-xs rounded-mars-sm transition-colors disabled:opacity-50"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            {refreshing
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : <RefreshCw className="w-3 h-3" />}
            Refresh
          </button>
          <Button onClick={handleDownloadAll} variant="secondary" size="sm">
            <Download className="w-3 h-3 mr-1" />
            Download all
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-2 pt-2 flex-shrink-0">
        <Tabs
          items={tabs}
          activeId={activeCat ?? ''}
          onChange={(id) => setActiveCat(id as ArtifactCategory)}
          variant="underline"
          size="sm"
        />
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-3">
        {activeCat === 'plots'
          ? <PlotsGrid items={items} onPreview={setPreviewing} />
          : <FileList items={items} onPreview={setPreviewing} />}
      </div>

      {/* Preview modal */}
      {previewing && (
        <PreviewModal
          item={previewing}
          onClose={() => setPreviewing(null)}
        />
      )}
    </div>
  )
}

// ─── Plots grid ────────────────────────────────────────────────────────────

function PlotsGrid({
  items,
  onPreview,
}: {
  items: ArtifactItem[]
  onPreview: (i: ArtifactItem) => void
}) {
  if (items.length === 0) {
    return <p className="text-xs text-center py-4" style={{ color: 'var(--mars-color-text-tertiary)' }}>
      No plots
    </p>
  }
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
      {items.map(item => (
        <div
          key={item.path}
          className="rounded-mars-sm border overflow-hidden flex flex-col"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          <button
            onClick={() => onPreview(item)}
            className="aspect-square flex items-center justify-center bg-white overflow-hidden"
            title="Click to preview"
          >
            {isImage(item)
              ? <img
                  src={imageUrl(item.path)}
                  alt={item.name}
                  className="max-w-full max-h-full object-contain"
                  loading="lazy"
                />
              : <FileText className="w-8 h-8 opacity-40" />}
          </button>
          <div
            className="px-2 py-1.5 flex items-center justify-between gap-1 text-xs"
            style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
          >
            <span className="truncate" title={item.name} style={{ color: 'var(--mars-color-text)' }}>
              {item.name}
            </span>
            <a
              href={downloadUrl(item.path)}
              title={`Download (${formatBytes(item.size)})`}
              className="flex-shrink-0 p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
            >
              <Download className="w-3 h-3" />
            </a>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── File list (code, data, reports, chats, planning, results) ────────────

function FileList({
  items,
  onPreview,
}: {
  items: ArtifactItem[]
  onPreview: (i: ArtifactItem) => void
}) {
  if (items.length === 0) {
    return <p className="text-xs text-center py-4" style={{ color: 'var(--mars-color-text-tertiary)' }}>
      No files
    </p>
  }
  return (
    <ul className="space-y-1">
      {items.map(item => (
        <li
          key={item.path}
          className="flex items-center gap-2 px-2 py-1.5 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)]"
        >
          <span className="truncate flex-1 text-sm font-mono" title={item.rel_path}
            style={{ color: 'var(--mars-color-text)' }}>
            {item.step !== null && (
              <span className="mr-2 text-xs px-1.5 py-0.5 rounded-mars-sm"
                style={{
                  backgroundColor: 'var(--mars-color-surface-overlay)',
                  color: 'var(--mars-color-text-tertiary)',
                }}>
                step {item.step}
              </span>
            )}
            {item.name}
          </span>
          <span className="text-xs flex-shrink-0" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            {formatBytes(item.size)}
          </span>
          <button
            onClick={() => onPreview(item)}
            title="Preview"
            className="p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg)]"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <Eye className="w-3.5 h-3.5" />
          </button>
          <a
            href={downloadUrl(item.path)}
            title="Download"
            className="p-1 rounded-mars-sm hover:bg-[var(--mars-color-bg)]"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <Download className="w-3.5 h-3.5" />
          </a>
        </li>
      ))}
    </ul>
  )
}

// ─── Preview modal ────────────────────────────────────────────────────────

function PreviewModal({ item, onClose }: { item: ArtifactItem; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const tooBig = item.size > INLINE_PREVIEW_MAX_BYTES
  const isImg = isImage(item)
  const isText = !isImg && !tooBig && (
    item.mime.startsWith('text/') ||
    /\.(json|jsonl|md|py|sh|csv|tsv|txt|html|htm|tex|yaml|yml|log|r|jl|ipynb|xml)$/i.test(item.name)
  )
  const isMarkdown = /\.md$/i.test(item.name)

  useEffect(() => {
    if (!isText) { setLoading(false); return }
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(getApiUrl(`/api/files/content?path=${encodeURIComponent(item.path)}`))
      .then(async r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const data = await r.json()
        if (cancelled) return
        // /api/files/content returns { content, ... } — fall back to raw text
        setText(typeof data === 'string' ? data : (data.content ?? JSON.stringify(data, null, 2)))
      })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [item, isText])

  return (
    <Modal open={true} onClose={onClose} title={item.name} size="lg">
      <div className="flex flex-col gap-3 max-h-[70vh]">
        <div className="flex items-center justify-between text-xs"
          style={{ color: 'var(--mars-color-text-tertiary)' }}>
          <span className="font-mono truncate">{item.rel_path}</span>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span>{formatBytes(item.size)}</span>
            <a
              href={downloadUrl(item.path)}
              className="flex items-center gap-1 px-2 py-1 rounded-mars-sm"
              style={{ color: 'var(--mars-color-text-secondary)' }}
            >
              <Download className="w-3 h-3" />
              Download
            </a>
          </div>
        </div>

        <div className="flex-1 overflow-auto rounded-mars-md border p-3"
          style={{ borderColor: 'var(--mars-color-border)' }}>
          {isImg ? (
            <img
              src={serveUrl(item.path)}
              alt={item.name}
              className="max-w-full max-h-[60vh] object-contain mx-auto block"
            />
          ) : tooBig ? (
            <p className="text-sm text-center py-8" style={{ color: 'var(--mars-color-text-secondary)' }}>
              File is {formatBytes(item.size)} — too large to preview inline.<br />
              Use the download button above.
            </p>
          ) : !isText ? (
            <p className="text-sm text-center py-8" style={{ color: 'var(--mars-color-text-secondary)' }}>
              Binary file — preview not available.<br />
              Use the download button above.
            </p>
          ) : loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin"
                style={{ color: 'var(--mars-color-text-tertiary)' }} />
            </div>
          ) : error ? (
            <p className="text-sm text-center py-8" style={{ color: 'var(--mars-color-error)' }}>
              {error}
            </p>
          ) : isMarkdown ? (
            <MarkdownRenderer content={text ?? ''} />
          ) : (
            <pre className="text-xs font-mono whitespace-pre-wrap break-words"
              style={{ color: 'var(--mars-color-text)' }}>
              {text}
            </pre>
          )}
        </div>
      </div>
    </Modal>
  )
}

