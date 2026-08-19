/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // MARS token-backed colors
        mars: {
          primary: 'var(--mars-color-primary)',
          'primary-hover': 'var(--mars-color-primary-hover)',
          'primary-subtle': 'var(--mars-color-primary-subtle)',
          accent: 'var(--mars-color-accent)',
          'accent-hover': 'var(--mars-color-accent-hover)',
          surface: 'var(--mars-color-surface)',
          'surface-raised': 'var(--mars-color-surface-raised)',
          'surface-overlay': 'var(--mars-color-surface-overlay)',
          bg: 'var(--mars-color-bg)',
          'bg-secondary': 'var(--mars-color-bg-secondary)',
          'bg-hover': 'var(--mars-color-bg-hover)',
          text: 'var(--mars-color-text)',
          'text-secondary': 'var(--mars-color-text-secondary)',
          'text-tertiary': 'var(--mars-color-text-tertiary)',
          border: 'var(--mars-color-border)',
          'border-strong': 'var(--mars-color-border-strong)',
          success: 'var(--mars-color-success)',
          warning: 'var(--mars-color-warning)',
          danger: 'var(--mars-color-danger)',
          info: 'var(--mars-color-info)',
        },
        // Preserve existing colors for backward compat during migration
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        console: {
          bg: '#1a1a1a',
          text: '#e5e5e5',
          success: '#22c55e',
          error: '#ef4444',
          warning: '#f59e0b',
          info: '#3b82f6',
        }
      },
      fontFamily: {
        sans: ['var(--mars-font-sans)'],
        mono: ['var(--mars-font-mono)'],
      },
      borderRadius: {
        'mars-sm': 'var(--mars-radius-sm)',
        'mars-md': 'var(--mars-radius-md)',
        'mars-lg': 'var(--mars-radius-lg)',
        'mars-xl': 'var(--mars-radius-xl)',
      },
      boxShadow: {
        'mars-sm': 'var(--mars-shadow-sm)',
        'mars-md': 'var(--mars-shadow-md)',
        'mars-lg': 'var(--mars-shadow-lg)',
        'mars-xl': 'var(--mars-shadow-xl)',
        'glow': 'var(--mars-shadow-glow)',
        'glow-sm': 'var(--mars-shadow-glow-sm)',
      },
      backgroundImage: {
        'brand-gradient': 'var(--mars-gradient-brand)',
        'brand-gradient-hover': 'var(--mars-gradient-brand-hover)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'fade-in': 'fade-in var(--mars-duration-slow) var(--mars-ease-standard) both',
        'slide-up': 'slide-up var(--mars-duration-slow) var(--mars-ease-standard) both',
        'scale-in': 'scale-in var(--mars-duration-normal) var(--mars-ease-standard) both',
        'shimmer': 'shimmer 2s linear infinite',
      },
      zIndex: {
        'dropdown': 'var(--mars-z-dropdown)',
        'sticky': 'var(--mars-z-sticky)',
        'nav': 'var(--mars-z-nav)',
        'modal-backdrop': 'var(--mars-z-modal-backdrop)',
        'modal': 'var(--mars-z-modal)',
        'toast': 'var(--mars-z-toast)',
        'tooltip': 'var(--mars-z-tooltip)',
      },
      transitionTimingFunction: {
        'mars': 'var(--mars-ease-standard)',
        'mars-bounce': 'var(--mars-ease-bounce)',
      },
      transitionDuration: {
        'mars-fast': 'var(--mars-duration-fast)',
        'mars-normal': 'var(--mars-duration-normal)',
        'mars-slow': 'var(--mars-duration-slow)',
      },
      spacing: {
        'sidenav': 'var(--mars-sidenav-width)',
        'sidenav-collapsed': 'var(--mars-sidenav-collapsed-width)',
        'topbar': 'var(--mars-topbar-height)',
      },
    },
  },
  plugins: [],
}
