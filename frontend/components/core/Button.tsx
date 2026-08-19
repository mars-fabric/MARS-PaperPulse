'use client'

import React, { forwardRef } from 'react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'gradient' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
  iconRight?: React.ReactNode
  fullWidth?: boolean
}

const variantClasses: Record<string, string> = {
  primary:
    'bg-[var(--mars-color-primary)] text-white border-transparent shadow-sm hover:bg-[var(--mars-color-primary-hover)] active:bg-[var(--mars-color-primary-active)]',
  gradient:
    'bg-brand-gradient text-white border-transparent shadow-glow-sm hover:shadow-glow hover:-translate-y-px active:translate-y-0',
  secondary:
    'bg-transparent text-[var(--mars-color-text)] border-[var(--mars-color-border-strong)] hover:bg-[var(--mars-color-bg-hover)] hover:border-[var(--mars-color-border-strong)] active:bg-[var(--mars-color-bg-active)]',
  ghost:
    'bg-transparent text-[var(--mars-color-text-secondary)] border-transparent hover:bg-[var(--mars-color-bg-hover)] hover:text-[var(--mars-color-text)] active:bg-[var(--mars-color-bg-active)]',
  danger:
    'bg-[var(--mars-color-danger)] text-white border-transparent hover:brightness-110 active:brightness-95',
}

const sizeClasses: Record<string, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-10 px-5 text-sm gap-2',
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    iconRight,
    fullWidth = false,
    disabled,
    className = '',
    children,
    ...props
  },
  ref
) {
  const isDisabled = disabled || loading

  return (
    <button
      ref={ref}
      disabled={isDisabled}
      className={`
        mars-focus-ring inline-flex items-center justify-center font-medium
        rounded-mars-md border transition-all duration-mars-fast ease-mars
        ${sizeClasses[size]}
        ${variantClasses[variant]}
        ${fullWidth ? 'w-full' : ''}
        ${isDisabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : 'cursor-pointer'}
        ${className}
      `}
      {...props}
    >
      {loading && (
        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="opacity-25" />
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="opacity-75" />
        </svg>
      )}
      {!loading && icon}
      {children}
      {iconRight}
    </button>
  )
})

export default Button
