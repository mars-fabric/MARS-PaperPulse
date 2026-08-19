'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { Send, Check, Loader2, AlertTriangle, Sparkles, MessageSquare } from 'lucide-react'
import type { RefinementMessage } from '@/types/deepresearch'

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

export default function RefinementChat({ messages, onSend, onApply, isLoading }: RefinementChatProps) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

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
        className="flex items-center gap-2.5 px-4 py-3 border-b flex-shrink-0"
        style={{ borderColor: 'var(--mars-color-border)', backgroundColor: 'var(--mars-color-surface)' }}
      >
        <div
          className="w-7 h-7 rounded-mars-md flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: 'var(--mars-color-primary-subtle)' }}
        >
          <Sparkles className="w-4 h-4" style={{ color: 'var(--mars-color-primary)' }} />
        </div>
        <div>
          <p
            className="text-sm font-semibold leading-tight"
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
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-3 mars-scrollbar"
        style={{ minHeight: 0 }}
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center text-center py-10 px-2">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mb-3"
              style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
            >
              <MessageSquare className="w-6 h-6" style={{ color: 'var(--mars-color-text-tertiary)' }} />
            </div>
            <p className="text-xs leading-relaxed max-w-[220px]" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              Ask the AI to refine the content. For example: &quot;Make the methodology section more specific&quot; or &quot;Focus on weak lensing approaches&quot;
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}>
            <div
              className="max-w-[85%] rounded-mars-lg px-3 py-2 text-xs"
              style={{
                backgroundColor: msg.role === 'user'
                  ? 'var(--mars-color-primary-subtle)'
                  : 'var(--mars-color-surface-overlay)',
                color: 'var(--mars-color-text)',
                border: msg.role === 'user'
                  ? '1px solid color-mix(in srgb, var(--mars-color-primary) 25%, transparent)'
                  : '1px solid var(--mars-color-border)',
              }}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.role === 'assistant' && (
                <>
                  <MethodBadge msg={msg} />
                  <button
                    onClick={() => onApply(msg.content)}
                    className="mars-focus-ring mt-2 inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-mars-sm transition-colors hover:bg-[var(--mars-color-primary-subtle)]"
                    style={{ color: 'var(--mars-color-primary)' }}
                  >
                    <Check className="w-3 h-3" />
                    Apply to editor
                  </button>
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
        style={{ borderColor: 'var(--mars-color-border)', backgroundColor: 'var(--mars-color-surface)' }}
      >
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe how to refine..."
            rows={2}
            className="mars-input flex-1 rounded-mars-md p-2.5 text-xs resize-none"
            disabled={sending || isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="mars-focus-ring p-2.5 rounded-mars-md transition-all disabled:cursor-not-allowed"
            style={{
              background: input.trim() ? 'var(--mars-gradient-brand)' : 'var(--mars-color-surface-overlay)',
              color: input.trim() ? 'white' : 'var(--mars-color-text-tertiary)',
              boxShadow: input.trim() ? 'var(--mars-shadow-glow-sm)' : 'none',
              opacity: sending ? 0.5 : 1,
            }}
            aria-label="Send refinement request"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  )
}
