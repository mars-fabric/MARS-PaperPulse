'use client'

import React, { useEffect, useRef, useState } from 'react'
import { Copy, Download, Maximize2, X } from 'lucide-react'

interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'success' | 'warning' | 'error' | 'debug'
  message: string
  details?: string
}

interface ModernConsoleViewerProps {
  logs?: LogEntry[]
  isLive?: boolean
  title?: string
  onCopy?: () => void
  onDownload?: () => void
  maxHeight?: string
}

const levelConfig: Record<string, { bg: string; border: string; dot: string; label: string }> = {
  info: {
    bg: 'rgba(59, 130, 246, 0.08)',
    border: 'rgba(59, 130, 246, 0.3)',
    dot: '#3B82F6',
    label: 'INFO',
  },
  success: {
    bg: 'rgba(34, 197, 94, 0.08)',
    border: 'rgba(34, 197, 94, 0.3)',
    dot: '#22C55E',
    label: 'SUCCESS',
  },
  warning: {
    bg: 'rgba(245, 158, 11, 0.08)',
    border: 'rgba(245, 158, 11, 0.3)',
    dot: '#F59E0B',
    label: 'WARN',
  },
  error: {
    bg: 'rgba(239, 68, 68, 0.08)',
    border: 'rgba(239, 68, 68, 0.3)',
    dot: '#EF4444',
    label: 'ERROR',
  },
  debug: {
    bg: 'rgba(139, 92, 246, 0.08)',
    border: 'rgba(139, 92, 246, 0.3)',
    dot: '#8B5CF6',
    label: 'DEBUG',
  },
}

export default function ModernConsoleViewer({
  logs = [],
  isLive = false,
  title = 'Console Output',
  onCopy,
  onDownload,
  maxHeight = '500px',
}: ModernConsoleViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [showCopyToast, setShowCopyToast] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  // Auto-scroll to latest log
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  const handleCopy = () => {
    const text = logs.map(log => `[${log.timestamp}] ${log.level.toUpperCase()}: ${log.message}`).join('\n')
    navigator.clipboard.writeText(text)
    setShowCopyToast(true)
    setTimeout(() => setShowCopyToast(false), 2000)
    onCopy?.()
  }

  const displayLogs = isExpanded ? logs : logs.slice(-50)

  return (
    <div
      className="rounded-lg border overflow-hidden flex flex-col"
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
        height: isExpanded ? '90vh' : maxHeight,
        maxHeight: isExpanded ? '90vh' : maxHeight,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3.5 border-b flex-shrink-0"
        style={{
          backgroundColor: 'var(--mars-color-surface-raised)',
          borderColor: 'var(--mars-color-border)',
        }}
      >
        <div className="flex items-center gap-3">
          {/* Live Indicator */}
          {isLive && (
            <div className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: '#EF4444' }}
              />
              <span className="text-xs font-semibold" style={{ color: '#EF4444' }}>
                LIVE
              </span>
            </div>
          )}
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {title}
          </span>
          <span className="text-xs px-2 py-1 rounded-full" style={{
            backgroundColor: 'rgba(255,255,255,0.1)',
            color: 'var(--mars-color-text-tertiary)',
          }}>
            {logs.length} lines
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {showCopyToast && (
            <span className="text-xs text-green-400">Copied!</span>
          )}
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
            style={{ color: 'var(--mars-color-text-secondary)' }}
            title="Copy to clipboard"
          >
            <Copy className="w-4 h-4" />
          </button>
          {onDownload && (
            <button
              onClick={onDownload}
              className="p-1.5 rounded-lg transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              title="Download logs"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded-lg transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
            style={{ color: 'var(--mars-color-text-secondary)' }}
            title={isExpanded ? 'Minimize' : 'Expand'}
          >
            {isExpanded ? <X className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Console Body */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto font-mono text-xs space-y-1 p-4"
        style={{
          backgroundColor: 'var(--mars-color-surface-sunken)',
        }}
      >
        {displayLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center">
            <div>
              <p style={{ color: 'var(--mars-color-text-tertiary)' }}>No logs available</p>
              <p style={{ color: 'var(--mars-color-text-disabled)', fontSize: '11px' }}>
                Logs will appear here as the task runs
              </p>
            </div>
          </div>
        ) : (
          displayLogs.map((log) => {
            const config = levelConfig[log.level]
            return (
              <div
                key={log.id}
                className="group p-3 rounded-lg border transition-all hover:border-opacity-100"
                style={{
                  backgroundColor: config.bg,
                  borderColor: config.border,
                  borderWidth: '1px',
                }}
              >
                <div className="flex items-start gap-3">
                  {/* Level Indicator */}
                  <div className="flex items-center gap-2 flex-shrink-0 pt-0.5">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: config.dot }}
                    />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className="text-[10px] font-bold uppercase tracking-wider flex-shrink-0"
                        style={{ color: config.dot }}
                      >
                        {config.label}
                      </span>
                      <span
                        className="text-[11px] flex-shrink-0"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}
                      >
                        {log.timestamp}
                      </span>
                    </div>
                    <p
                      className="text-xs mt-1.5 leading-relaxed break-words"
                      style={{ color: 'var(--mars-color-text)' }}
                    >
                      {log.message}
                    </p>
                    {log.details && (
                      <pre
                        className="text-[10px] mt-2 p-2 rounded bg-[rgba(0,0,0,0.2)] overflow-x-auto"
                        style={{ color: 'var(--mars-color-text-secondary)' }}
                      >
                        {log.details}
                      </pre>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}

        {/* Live Indicator at Bottom */}
        {isLive && logs.length > 0 && (
          <div className="flex items-center justify-center gap-2 py-4">
            <div
              className="w-1.5 h-1.5 rounded-full animate-pulse"
              style={{ backgroundColor: '#8B5CF6' }}
            />
            <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              Awaiting new logs...
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
