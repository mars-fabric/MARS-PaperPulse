'use client'

import React, { useRef, useEffect } from 'react'
import { Loader2, CheckCircle2 } from 'lucide-react'

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
      <div className="flex items-center gap-2.5">
        {isExecuting ? (
          <>
            <Loader2
              className="w-4 h-4 animate-spin"
              style={{ color: 'var(--mars-color-primary)' }}
            />
            <span
              className="text-sm font-semibold"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Running {stageName}...
            </span>
          </>
        ) : (
          <>
            <span
              className="inline-flex items-center justify-center w-5 h-5 rounded-full"
              style={{ backgroundColor: 'var(--mars-color-success-subtle)' }}
            >
              <CheckCircle2 className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-success)' }} />
            </span>
            <span
              className="text-sm font-semibold"
              style={{ color: 'var(--mars-color-success)' }}
            >
              {stageName} complete
            </span>
          </>
        )}
      </div>

      {/* Console output — terminal aesthetic */}
      <div
        className="rounded-mars-lg border overflow-hidden"
        style={{ borderColor: 'var(--mars-color-border)', boxShadow: 'var(--mars-shadow-sm)' }}
      >
        {/* Faux terminal title bar */}
        <div
          className="flex items-center gap-1.5 px-3 py-2 border-b"
          style={{ backgroundColor: 'var(--mars-color-console-bg)', borderColor: 'rgba(255,255,255,0.06)' }}
        >
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: '#ff5f57' }} />
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: '#febc2e' }} />
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: '#28c840' }} />
          <span className="ml-2 text-[11px] font-mono" style={{ color: 'rgba(229,229,229,0.5)' }}>
            {stageName.toLowerCase().replace(/\s+/g, '-')}.log
          </span>
        </div>
        <div
          ref={scrollRef}
          className="p-4 font-mono text-xs overflow-y-auto mars-scrollbar console-scrollbar leading-relaxed"
          style={{
            backgroundColor: 'var(--mars-color-console-bg)',
            color: 'var(--mars-color-console-text)',
            maxHeight: '400px',
            minHeight: '200px',
          }}
        >
          {consoleOutput.length === 0 ? (
            <p className="flex items-center gap-2" style={{ color: 'rgba(229,229,229,0.45)' }}>
              {isExecuting && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
              Waiting for output...
            </p>
          ) : (
            consoleOutput.map((line, i) => (
              <div key={i} className="py-0.5 whitespace-pre-wrap break-words">
                {line}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
