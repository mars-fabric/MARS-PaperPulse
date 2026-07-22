'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Copy, Download, ChevronUp } from 'lucide-react'

interface LogTab {
  id: string
  label: string
  count: number
}

interface MacOSTerminalViewerProps {
  stageNumber: number
  stageName: string
  logs: string[]
  isExecuting: boolean
  tabs?: LogTab[]
  activeTab?: string
  onTabChange?: (tabId: string) => void
  title?: string
}

export default function MacOSTerminalViewer({
  stageNumber,
  stageName,
  logs,
  isExecuting,
  tabs,
  activeTab = 'all',
  onTabChange,
  title,
}: MacOSTerminalViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [copyFeedback, setCopyFeedback] = useState(false)

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current && !isExpanded) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, isExpanded])

  const handleCopy = () => {
    const text = logs.join('\n')
    navigator.clipboard.writeText(text).then(() => {
      setCopyFeedback(true)
      setTimeout(() => setCopyFeedback(false), 2000)
    })
  }

  const handleDownload = () => {
    const text = logs.join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `stage-${stageNumber}-${stageName.toLowerCase().replace(/\s+/g, '-')}.log`
    a.click()
    URL.revokeObjectURL(url)
  }

  const defaultTabs: LogTab[] = tabs || [
    { id: 'all', label: 'All output', count: logs.length },
  ]

  const displayLogs = logs.slice(0, isExpanded ? logs.length : 50)

  return (
    <div className="w-full space-y-3">
      {/* macOS Terminal Header */}
      <div
        className="rounded-t-lg p-0 overflow-hidden"
        style={{
          backgroundColor: '#1E1E1E',
        }}
      >
        {/* macOS Traffic Lights */}
        <div className="flex items-center gap-2 px-4 py-2.5 border-b" style={{ borderColor: '#333333' }}>
          <div className="flex gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: '#FF5F56' }}
            />
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: '#FFBD2E' }}
            />
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: '#27C93F' }}
            />
          </div>
          <span className="ml-4 text-xs font-medium" style={{ color: '#888888' }}>
            {`STAGE ${stageNumber}: ${stageName.toUpperCase()}`}
          </span>
        </div>

        {/* Tabs */}
        {defaultTabs.length > 1 && (
          <div className="flex border-b px-4" style={{ borderColor: '#333333' }}>
            {defaultTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => onTabChange?.(tab.id)}
                className="px-3 py-2 text-xs font-medium border-b-2 transition-colors"
                style={{
                  color: activeTab === tab.id ? '#00D4FF' : '#888888',
                  borderColor: activeTab === tab.id ? '#00D4FF' : 'transparent',
                  backgroundColor: activeTab === tab.id ? 'rgba(0, 212, 255, 0.05)' : 'transparent',
                }}
              >
                <span className="flex items-center gap-2">
                  {tab.label}
                  <span
                    className="px-1.5 py-0.5 rounded text-xs"
                    style={{
                      backgroundColor: '#333333',
                      color: '#888888',
                    }}
                  >
                    {tab.count}
                  </span>
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Terminal Output Area */}
      <div
        ref={scrollRef}
        className="rounded-b-lg p-4 font-mono text-sm overflow-y-auto transition-all"
        style={{
          backgroundColor: '#1A1A1A',
          color: '#E0E0E0',
          height: isExpanded ? '600px' : '300px',
          minHeight: isExpanded ? '600px' : '300px',
          borderLeft: '1px solid #333333',
          borderRight: '1px solid #333333',
          borderBottom: '1px solid #333333',
        }}
      >
        {logs.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <span style={{ color: '#666666' }}>
              {isExecuting ? 'Waiting for output...' : 'No output yet'}
            </span>
          </div>
        ) : (
          <div className="space-y-1">
            {displayLogs.map((line, idx) => (
              <div
                key={idx}
                className="whitespace-pre-wrap break-words text-xs leading-relaxed"
                style={{
                  color: line.toLowerCase().includes('error') ? '#FF6B6B' : 
                         line.toLowerCase().includes('success') || line.toLowerCase().includes('✓') ? '#51CF66' :
                         line.toLowerCase().includes('warning') ? '#FFD93D' :
                         line.toLowerCase().includes('debug') ? '#845EF7' :
                         '#E0E0E0',
                }}
              >
                {line}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="flex items-center justify-between px-4 py-3 rounded-b-lg border" style={{ borderColor: '#333333', backgroundColor: '#1E1E1E' }}>
        <div className="flex items-center gap-2">
          {isExecuting && (
            <div className="flex items-center gap-1.5">
              <div
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: '#FF5F56' }}
              />
              <span className="text-xs font-medium" style={{ color: '#FF5F56' }}>
                LIVE
              </span>
            </div>
          )}
          <span className="text-xs" style={{ color: '#666666' }}>
            {logs.length} line{logs.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {copyFeedback && (
            <span className="text-xs" style={{ color: '#51CF66' }}>
              ✓ Copied
            </span>
          )}

          <button
            onClick={handleCopy}
            title="Copy logs"
            className="p-1.5 rounded transition-colors hover:opacity-80"
            style={{
              color: '#888888',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
            }}
          >
            <Copy className="w-4 h-4" />
          </button>

          <button
            onClick={handleDownload}
            title="Download logs"
            className="p-1.5 rounded transition-colors hover:opacity-80"
            style={{
              color: '#888888',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
            }}
          >
            <Download className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Collapse' : 'Expand'}
            className="p-1.5 rounded transition-all hover:opacity-80"
            style={{
              color: '#00D4FF',
              backgroundColor: 'rgba(0, 212, 255, 0.1)',
              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
            }}
          >
            <ChevronUp className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
