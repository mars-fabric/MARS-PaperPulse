'use client'

import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { Send, Check, Loader2, AlertTriangle, GitCompare, ChevronDown, ChevronRight } from 'lucide-react'
import type { RefinementMessage } from '@/types/deepresearch'
import { diffLines, diffStats, type DiffLine } from '@/lib/lineDiff'

interface RefinementChatProps {
  messages: RefinementMessage[]
  onSend: (message: string) => Promise<string | null>
  onApply: (content: string) => void
  isLoading?: boolean
}

/**
 * Small inline badge showing how the refinement was produced.
 * - diff with 0 failures  → green "N edit(s) applied"
 * - diff with failures     → amber warning
 * - fallback               → neutral "full rewrite"
 */
function MethodBadge({ msg }: { msg: RefinementMessage }) {
  if (!msg.method) return null

  if (msg.method === 'diff') {
    const applied = msg.edits_applied ?? 0
    const failed = msg.edits_failed ?? 0

    return (
      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        <span
          className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded"
          style={{
            backgroundColor: 'var(--mars-color-success-subtle, #dcfce7)',
            color: 'var(--mars-color-success, #16a34a)',
          }}
        >
          <Check className="w-2.5 h-2.5" />
          {applied} edit{applied !== 1 ? 's' : ''} applied
        </span>
        {failed > 0 && (
          <span
            className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded"
            style={{
              backgroundColor: 'var(--mars-color-warning-subtle, #fef9c3)',
              color: 'var(--mars-color-warning, #ca8a04)',
            }}
          >
            <AlertTriangle className="w-2.5 h-2.5" />
            {failed} edit{failed !== 1 ? 's' : ''} could not be located
          </span>
        )}
      </div>
    )
  }

  // fallback method
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded mt-1.5"
      style={{
        backgroundColor: 'var(--mars-color-surface-overlay)',
        color: 'var(--mars-color-text-secondary)',
      }}
    >
      full rewrite (diff not possible)
    </span>
  )
}

/**
 * Inline before-vs-after view for an assistant refinement.
 *
 * Renders a compact line-by-line diff. Equal lines are collapsed into a
 * "… N unchanged …" marker so users can focus on what actually changed.
 */
function DiffView({ original, refined }: { original: string; refined: string }) {
  const lines = useMemo<DiffLine[]>(() => diffLines(original, refined), [original, refined])
  const stats = useMemo(() => diffStats(lines), [lines])

  // Collapse runs of >3 unchanged lines into a single elision marker.
  const rendered: Array<DiffLine | { op: 'gap'; count: number }> = []
  let runStart = -1
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].op === 'equal') {
      if (runStart < 0) runStart = i
      continue
    }
    if (runStart >= 0) {
      const run = i - runStart
      if (run > 3) {
        rendered.push(lines[runStart])
        rendered.push({ op: 'gap', count: run - 2 })
        rendered.push(lines[i - 1])
      } else {
        for (let k = runStart; k < i; k++) rendered.push(lines[k])
      }
      runStart = -1
    }
    rendered.push(lines[i])
  }
  if (runStart >= 0) {
    const run = lines.length - runStart
    if (run > 3) {
      rendered.push(lines[runStart])
      rendered.push({ op: 'gap', count: run - 2 })
      rendered.push(lines[lines.length - 1])
    } else {
      for (let k = runStart; k < lines.length; k++) rendered.push(lines[k])
    }
  }

  return (
    <div
      className="mt-2 rounded border overflow-hidden"
      style={{ borderColor: 'var(--mars-color-border)', backgroundColor: 'var(--mars-color-surface)' }}
    >
      <div
        className="flex items-center justify-between px-2 py-1 text-[10px] border-b"
        style={{
          borderColor: 'var(--mars-color-border)',
          backgroundColor: 'var(--mars-color-surface-overlay)',
          color: 'var(--mars-color-text-secondary)',
        }}
      >
        <span className="font-medium">Changes vs your prior content</span>
        <span>
          <span style={{ color: 'var(--mars-color-success, #16a34a)' }}>+{stats.added}</span>
          {' '}
          <span style={{ color: 'var(--mars-color-danger, #dc2626)' }}>-{stats.removed}</span>
          {' '}
          <span style={{ opacity: 0.7 }}>={stats.unchanged}</span>
        </span>
      </div>
      <pre
        className="m-0 text-[10px] leading-snug overflow-x-auto"
        style={{ color: 'var(--mars-color-text)', maxHeight: '260px', whiteSpace: 'pre' }}
      >
        {rendered.map((row, idx) => {
          if ('count' in row) {
            return (
              <div
                key={`gap-${idx}`}
                className="px-2 py-0.5 text-center"
                style={{ color: 'var(--mars-color-text-tertiary)', backgroundColor: 'transparent' }}
              >
                ··· {row.count} unchanged line{row.count !== 1 ? 's' : ''} ···
              </div>
            )
          }
          const bg =
            row.op === 'add'    ? 'rgba(34,197,94,0.12)' :
            row.op === 'remove' ? 'rgba(239,68,68,0.12)' :
            'transparent'
          const sigil = row.op === 'add' ? '+' : row.op === 'remove' ? '-' : ' '
          const fg =
            row.op === 'add'    ? 'var(--mars-color-success, #16a34a)' :
            row.op === 'remove' ? 'var(--mars-color-danger,  #dc2626)' :
            'var(--mars-color-text-secondary)'
          return (
            <div
              key={`${row.op}-${idx}`}
              className="px-2"
              style={{ backgroundColor: bg, color: fg }}
            >
              <span style={{ display: 'inline-block', width: '1ch', textAlign: 'center', opacity: 0.7 }}>{sigil}</span>
              {' '}
              <span style={{ color: 'var(--mars-color-text)' }}>{row.text || ' '}</span>
            </div>
          )
        })}
      </pre>
    </div>
  )
}

export default function RefinementChat({ messages, onSend, onApply, isLoading }: RefinementChatProps) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [diffExpanded, setDiffExpanded] = useState<Record<string, boolean>>({})
  const scrollRef = useRef<HTMLDivElement>(null)

  const toggleDiff = useCallback((id: string) => {
    setDiffExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = useCallback(async () => {
    if (!input.trim() || sending) return
    const msg = input.trim()
    setInput('')
    setSending(true)
    await onSend(msg)
    setSending(false)
  }, [input, sending, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-4 py-3 border-b flex-shrink-0"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <p
          className="text-sm font-medium"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Refinement Chat
        </p>
        <p
          className="text-xs"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          Ask the AI to modify or improve the content
        </p>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-3"
        style={{ minHeight: 0 }}
      >
        {messages.length === 0 && (
          <p
            className="text-xs text-center py-8"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Ask the AI to refine the content. For example:
            &quot;Make the methodology section more specific&quot;
            or &quot;Focus on weak lensing approaches&quot;
          </p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className="max-w-[85%] rounded-mars-md px-3 py-2 text-xs"
              style={{
                backgroundColor: msg.role === 'user'
                  ? 'var(--mars-color-primary-subtle)'
                  : 'var(--mars-color-surface-overlay)',
                color: 'var(--mars-color-text)',
              }}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.role === 'assistant' && (
                <>
                  <MethodBadge msg={msg} />
                  <div className="mt-2 flex items-center gap-3 flex-wrap">
                    <button
                      onClick={() => onApply(msg.content)}
                      className="flex items-center gap-1 text-xs font-medium"
                      style={{ color: 'var(--mars-color-primary)' }}
                    >
                      <Check className="w-3 h-3" />
                      Apply to editor
                    </button>
                    {msg.original_content !== undefined && msg.original_content !== msg.content && (
                      <button
                        onClick={() => toggleDiff(msg.id)}
                        className="flex items-center gap-1 text-xs font-medium"
                        style={{ color: 'var(--mars-color-text-secondary)' }}
                        title="Show line-by-line changes vs your prior content"
                      >
                        {diffExpanded[msg.id]
                          ? <ChevronDown className="w-3 h-3" />
                          : <ChevronRight className="w-3 h-3" />}
                        <GitCompare className="w-3 h-3" />
                        {diffExpanded[msg.id] ? 'Hide diff' : 'Show diff'}
                      </button>
                    )}
                  </div>
                  {diffExpanded[msg.id] && msg.original_content !== undefined && (
                    <DiffView original={msg.original_content} refined={msg.content} />
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div
              className="rounded-mars-md px-3 py-2"
              style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
            >
              <Loader2
                className="w-4 h-4 animate-spin"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div
        className="px-4 py-3 border-t flex-shrink-0"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe how to refine..."
            rows={2}
            className="flex-1 rounded-mars-md border p-2 text-xs resize-none outline-none"
            style={{
              backgroundColor: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
            disabled={sending || isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="p-2 rounded-mars-md transition-colors"
            style={{
              backgroundColor: input.trim() ? 'var(--mars-color-primary)' : 'var(--mars-color-surface-overlay)',
              color: input.trim() ? 'white' : 'var(--mars-color-text-tertiary)',
              opacity: sending ? 0.5 : 1,
            }}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
