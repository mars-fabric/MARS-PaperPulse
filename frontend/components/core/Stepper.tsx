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

export default function Stepper({ steps, orientation = 'horizontal', size = 'md', onStepClick }: StepperProps) {
  const isVertical = orientation === 'vertical'
  const dotSize = size === 'sm' ? 'w-8 h-8' : 'w-9 h-9'

  const isClickable = (s: StepperStep) =>
    !!onStepClick && (s.status === 'completed' || s.status === 'active' || s.status === 'failed')

  return (
    <div
      className={`flex ${isVertical ? 'flex-col' : 'items-start'}`}
      role="list"
    >
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1
        const clickable = isClickable(step)
        const done = step.status === 'completed'
        const active = step.status === 'active'
        const failed = step.status === 'failed'
        const skipped = step.status === 'skipped'

        const dotStyle: React.CSSProperties = failed
          ? { backgroundColor: 'var(--mars-color-danger-subtle)', border: '2px solid var(--mars-color-danger)', color: 'var(--mars-color-danger)' }
          : done
            ? { backgroundColor: 'var(--mars-color-primary)', border: '2px solid var(--mars-color-primary)', color: '#fff', boxShadow: 'var(--mars-shadow-glow-sm)' }
            : active
              ? { backgroundColor: 'var(--mars-color-surface-raised)', border: '2px solid var(--mars-color-primary)', color: 'var(--mars-color-primary)', boxShadow: '0 0 0 4px var(--mars-color-primary-subtle)' }
              : { backgroundColor: 'var(--mars-color-surface-overlay)', border: '2px solid var(--mars-color-border)', color: 'var(--mars-color-text-tertiary)' }

        const dotContent = failed ? <X className="w-4 h-4" />
          : done ? <Check className="w-4 h-4" />
            : skipped ? <Minus className="w-4 h-4" />
              : active ? <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
                : index + 1

        // Connector after a completed step is filled with the brand color
        const connectorColor = done ? 'var(--mars-color-primary)' : 'var(--mars-color-border)'

        return (
          <div
            key={step.id}
            className={`flex ${isVertical ? 'flex-row' : 'flex-col items-center'} ${!isLast ? 'flex-1' : ''}`}
            role="listitem"
          >
            <div className={`flex ${isVertical ? 'flex-col items-center' : 'items-center w-full'}`}>
              {/* Step Dot */}
              <div
                className={`${dotSize} flex-shrink-0 rounded-full flex items-center justify-center
                  text-xs font-semibold transition-all duration-mars-normal ease-mars
                  ${clickable ? 'cursor-pointer hover:scale-110 mars-focus-ring' : ''}`}
                style={dotStyle}
                onClick={() => { if (clickable) onStepClick!(index) }}
                onKeyDown={(e) => { if (clickable && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onStepClick!(index) } }}
                role={clickable ? 'button' : undefined}
                tabIndex={clickable ? 0 : undefined}
                aria-current={active ? 'step' : undefined}
                aria-label={`${step.label}${done ? ' (completed)' : active ? ' (current)' : failed ? ' (failed)' : ''}`}
              >
                {dotContent}
              </div>

              {/* Connector Line */}
              {!isLast && (
                <div
                  className={`${isVertical ? 'w-0.5 min-h-[24px] mx-auto my-1' : 'flex-1 h-0.5 mx-2'} rounded-full transition-colors duration-500`}
                  style={{ backgroundColor: connectorColor }}
                />
              )}
            </div>

            {/* Label */}
            <div
              className={`${isVertical ? 'ml-3 pb-6' : 'mt-2.5 text-center'} ${clickable ? 'cursor-pointer' : ''}`}
              onClick={() => { if (clickable) onStepClick!(index) }}
            >
              <p
                className={`${size === 'sm' ? 'text-xs' : 'text-sm'} font-medium transition-colors`}
                style={{
                  color: active
                    ? 'var(--mars-color-text)'
                    : done
                      ? 'var(--mars-color-text-secondary)'
                      : 'var(--mars-color-text-tertiary)',
                }}
              >
                {step.label}
              </p>
              {step.description && (
                <p
                  className="text-xs mt-0.5"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
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

