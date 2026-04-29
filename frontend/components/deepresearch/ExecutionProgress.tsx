'use client'

import React, { useRef, useEffect } from 'react'
import { Loader2, CheckCircle2, Terminal } from 'lucide-react'

interface ExecutionProgressProps {
  consoleOutput: string[]
  isExecuting: boolean
  stageName: string
}

export default function ExecutionProgress({ consoleOutput, isExecuting, stageName }: ExecutionProgressProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [consoleOutput])

  return (
    <div className="space-y-3">
      {/* Status indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {isExecuting ? (
            <>
              <span className="relative flex w-2.5 h-2.5">
                <span
                  className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                  style={{ backgroundColor: 'var(--mars-color-primary)' }}
                />
                <span
                  className="relative inline-flex rounded-full h-2.5 w-2.5"
                  style={{ backgroundColor: 'var(--mars-color-primary)' }}
                />
              </span>
              <span
                className="text-sm font-semibold"
                style={{ color: 'var(--mars-color-text)' }}
              >
                Running {stageName}
              </span>
              <span className="inline-flex items-center gap-0.5" aria-label="thinking">
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--mars-color-primary)', animationDelay: '0ms' }} />
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--mars-color-primary)', animationDelay: '120ms' }} />
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--mars-color-primary)', animationDelay: '240ms' }} />
              </span>
            </>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4" style={{ color: 'var(--mars-color-success)' }} />
              <span
                className="text-sm font-semibold"
                style={{ color: 'var(--mars-color-success)' }}
              >
                {stageName} complete
              </span>
            </>
          )}
        </div>
        <span className="text-[10px] font-mono tabular-nums" style={{ color: 'var(--mars-color-text-tertiary)' }}>
          {consoleOutput.length} {consoleOutput.length === 1 ? 'line' : 'lines'}
        </span>
      </div>

      {/* Terminal-style console */}
      <div
        className="rounded-xl border overflow-hidden"
        style={{
          borderColor: 'var(--mars-color-border)',
          boxShadow: '0 8px 24px -12px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04)',
        }}
      >
        {/* Terminal title bar */}
        <div
          className="flex items-center gap-2 px-3 py-2 border-b"
          style={{
            backgroundColor: 'var(--mars-color-surface-raised)',
            borderColor: 'var(--mars-color-border)',
          }}
        >
          {/* macOS-style traffic dots */}
          <div className="flex gap-1.5 mr-1">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: '#ef4444' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: '#f59e0b' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: '#22c55e' }} />
          </div>
          <Terminal className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-tertiary)' }} />
          <span className="text-[11px] font-mono" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            paperpulse — {stageName.toLowerCase()}
          </span>
          {isExecuting && (
            <span
              className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full"
              style={{
                background: 'rgba(139, 92, 246, 0.15)',
                color: 'var(--mars-color-primary)',
                border: '1px solid rgba(139, 92, 246, 0.30)',
              }}
            >
              LIVE
            </span>
          )}
        </div>

        {/* Console body */}
        <div
          ref={scrollRef}
          className="mars-scrollbar p-4 font-mono text-xs overflow-y-auto leading-relaxed"
          style={{
            backgroundColor: 'var(--mars-color-console-bg)',
            color: 'var(--mars-color-console-text)',
            maxHeight: '420px',
            minHeight: '220px',
          }}
        >
          {consoleOutput.length === 0 ? (
            <div className="flex items-center gap-2" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Waiting for output<span className="animate-pulse">…</span></span>
            </div>
          ) : (
            consoleOutput.map((line, i) => (
              <div key={i} className="py-0.5 flex gap-2">
                <span className="select-none flex-shrink-0 w-8 text-right tabular-nums" style={{ color: 'var(--mars-color-text-disabled)' }}>
                  {i + 1}
                </span>
                <span className="flex-1 break-words whitespace-pre-wrap">{line}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
