'use client'

import React from 'react'
import { Check, X, Minus } from 'lucide-react'

export interface StepperStep {
  id: string
  label: string
  status: 'pending' | 'active' | 'completed' | 'failed' | 'skipped'
  description?: string
}

export interface StepperProps {
  steps: StepperStep[]
  orientation?: 'horizontal' | 'vertical'
  size?: 'sm' | 'md'
  onStepClick?: (index: number) => void
}

const statusConfig: Record<string, { bg: string; border: string; icon?: React.ReactNode }> = {
  pending: {
    bg: 'var(--mars-color-surface-overlay)',
    border: 'var(--mars-color-border)',
  },
  active: {
    bg: 'var(--mars-color-primary-subtle)',
    border: 'var(--mars-color-primary)',
  },
  completed: {
    bg: 'var(--mars-color-success-subtle)',
    border: 'var(--mars-color-success)',
    icon: <Check className="w-3.5 h-3.5" />,
  },
  failed: {
    bg: 'var(--mars-color-danger-subtle)',
    border: 'var(--mars-color-danger)',
    icon: <X className="w-3.5 h-3.5" />,
  },
  skipped: {
    bg: 'var(--mars-color-surface-overlay)',
    border: 'var(--mars-color-border)',
    icon: <Minus className="w-3.5 h-3.5" />,
  },
}

export default function Stepper({ steps, orientation = 'horizontal', size = 'md', onStepClick }: StepperProps) {
  const isVertical = orientation === 'vertical'
  const dotSizeClass = size === 'sm' ? 'w-7 h-7' : 'w-9 h-9'
  // px values used to vertically align the connector hairline with the dot's
  // center. h-0.5 = 2px → margin = (dotPx / 2) - 1.
  const connectorMarginTop = size === 'sm' ? 13 : 17

  // Vertical layout — keeps the previous "label to the right of dot" form
  if (isVertical) {
    return (
      <div className="flex flex-col" role="list">
        {steps.map((step, index) => {
          const config = statusConfig[step.status]
          const isLast = index === steps.length - 1
          const isActive = step.status === 'active'
          const isCompleted = step.status === 'completed'
          const isFailed = step.status === 'failed'
          const clickable = !!onStepClick && (isCompleted || isActive || isFailed)

          return (
            <div key={step.id} className="flex flex-row" role="listitem">
              <div className="flex flex-col items-center">
                <StepDot
                  index={index}
                  size={dotSizeClass}
                  isActive={isActive}
                  isCompleted={isCompleted}
                  isFailed={isFailed}
                  config={config}
                  label={step.label}
                  clickable={clickable}
                  onClick={() => { if (clickable && onStepClick) onStepClick(index) }}
                />
                {!isLast && (
                  <div
                    className="w-0.5 min-h-[28px] my-1"
                    style={{ backgroundColor: isCompleted ? '#22c55e' : 'var(--mars-color-surface-overlay)' }}
                  />
                )}
              </div>
              <div
                className={`ml-3 pb-6 ${clickable ? 'cursor-pointer group' : ''}`}
                onClick={() => { if (clickable && onStepClick) onStepClick(index) }}
                title={clickable ? `Go to ${step.label}` : undefined}
              >
                <p
                  className={`${size === 'sm' ? 'text-xs' : 'text-sm'} font-semibold tracking-tight transition-colors ${clickable ? 'group-hover:text-[var(--mars-color-primary)]' : ''}`}
                  style={{
                    color: (isActive || isCompleted) ? 'var(--mars-color-text)' : 'var(--mars-color-text-tertiary)',
                  }}
                >
                  {step.label}
                </p>
                {step.description && (
                  <p className="text-xs mt-0.5" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                    {step.description}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // Horizontal layout — dots flush with the connectors. Labels are
  // absolutely positioned below each dot so a wide label like "Method
  // Development" can't push its column out and break the connector line.
  // The parent gets bottom padding to reserve space for the floating labels.
  return (
    <div className="flex items-start relative" role="list" style={{ paddingBottom: size === 'sm' ? 28 : 32 }}>
      {steps.map((step, index) => {
        const config = statusConfig[step.status]
        const isLast = index === steps.length - 1
        const isActive = step.status === 'active'
        const isCompleted = step.status === 'completed'
        const isFailed = step.status === 'failed'
        const nextStep = !isLast ? steps[index + 1] : null
        const nextIsCompletedOrActive = !!nextStep && (nextStep.status === 'completed' || nextStep.status === 'active')
        const clickable = !!onStepClick && (isCompleted || isActive || isFailed)

        return (
          <React.Fragment key={step.id}>
            {/* Dot wrapper — tight to the dot, label floats below absolutely */}
            <div className="relative flex-shrink-0" role="listitem">
              <StepDot
                index={index}
                size={dotSizeClass}
                isActive={isActive}
                isCompleted={isCompleted}
                isFailed={isFailed}
                config={config}
                label={step.label}
                clickable={clickable}
                onClick={() => { if (clickable && onStepClick) onStepClick(index) }}
              />
              {/* Absolutely-positioned label so it doesn't widen the column */}
              <div
                className={`absolute left-1/2 -translate-x-1/2 text-center whitespace-nowrap ${clickable ? 'cursor-pointer group' : ''}`}
                style={{ top: 'calc(100% + 8px)' }}
                onClick={() => { if (clickable && onStepClick) onStepClick(index) }}
                title={clickable ? `Go to ${step.label}` : undefined}
              >
                <p
                  className={`${size === 'sm' ? 'text-xs' : 'text-sm'} font-semibold tracking-tight transition-colors ${clickable ? 'group-hover:text-[var(--mars-color-primary)]' : ''}`}
                  style={{
                    color: (isActive || isCompleted) ? 'var(--mars-color-text)' : 'var(--mars-color-text-tertiary)',
                  }}
                >
                  {step.label}
                </p>
                {step.description && (
                  <p className="text-[10px] mt-0.5" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                    {step.description}
                  </p>
                )}
              </div>
            </div>

            {/* Connector — flush with both adjacent dots */}
            {!isLast && (
              <div
                className="flex-1 relative overflow-hidden rounded-full"
                style={{
                  height: '2px',
                  marginTop: `${connectorMarginTop}px`,
                  backgroundColor: 'var(--mars-color-surface-overlay)',
                }}
              >
                <div
                  className="absolute inset-0 rounded-full transition-all duration-500"
                  style={{
                    background: isCompleted
                      ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                      : isActive
                        ? 'linear-gradient(90deg, #22c55e, #8b5cf6)'
                        : 'transparent',
                    width: isCompleted ? '100%' : (isActive && nextIsCompletedOrActive) ? '100%' : isActive ? '50%' : '0%',
                    boxShadow: (isCompleted || isActive) ? '0 0 8px rgba(99, 102, 241, 0.45)' : 'none',
                  }}
                />
              </div>
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ─── Internal: single dot ──────────────────────────────────────────────────

interface StepDotProps {
  index: number
  size: string
  isActive: boolean
  isCompleted: boolean
  isFailed: boolean
  config: { bg: string; border: string; icon?: React.ReactNode }
  label: string
  clickable: boolean
  onClick: () => void
}

function StepDot({ index, size, isActive, isCompleted, isFailed, config, label, clickable, onClick }: StepDotProps) {
  return (
    <div className="relative flex-shrink-0">
      {isActive && (
        <span
          aria-hidden
          className="absolute inset-0 rounded-full animate-ping"
          style={{ background: 'radial-gradient(circle, rgba(139, 92, 246, 0.45), transparent 70%)' }}
        />
      )}
      <div
        className={`${size} relative rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${clickable ? 'cursor-pointer hover:scale-110 hover:brightness-110' : ''}`}
        style={{
          background: isActive
            ? 'linear-gradient(135deg, #8b5cf6, #6366f1)'
            : isCompleted
              ? 'linear-gradient(135deg, #22c55e, #16a34a)'
              : config.bg,
          border: isActive ? '2px solid transparent' : `2px solid ${config.border}`,
          color: (isActive || isCompleted) ? 'white' : isFailed ? 'var(--mars-color-danger)' : 'var(--mars-color-text-tertiary)',
          boxShadow: isActive
            ? '0 0 0 4px rgba(139, 92, 246, 0.18), 0 4px 14px rgba(99, 102, 241, 0.45)'
            : isCompleted
              ? '0 2px 8px rgba(34, 197, 94, 0.30)'
              : 'none',
        }}
        onClick={onClick}
        onKeyDown={(e) => {
          if (clickable && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            onClick()
          }
        }}
        role={clickable ? 'button' : undefined}
        tabIndex={clickable ? 0 : undefined}
        title={clickable ? `Go to ${label}` : undefined}
        aria-label={clickable ? `Go to ${label}` : label}
      >
        {config.icon || (isActive ? (
          <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
        ) : (
          index + 1
        ))}
      </div>
    </div>
  )
}
