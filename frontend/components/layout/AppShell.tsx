'use client'

import { ReactNode } from 'react'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--mars-color-bg)' }}>
      {/* Skip-to-content link (a11y) */}
      <a href="#mars-main-content" className="mars-skip-link">
        Skip to main content
      </a>

      {/* Content Area - TopBar is now rendered inside page.tsx for tighter control */}
      <main
        id="mars-main-content"
        role="main"
        className="flex-1 min-h-0 overflow-hidden flex flex-col"
        style={{ backgroundColor: 'var(--mars-color-bg)' }}
      >
        {children}
      </main>

      {/* Live region for screen reader announcements */}
      <div aria-live="polite" aria-atomic="true" className="mars-live-region" id="mars-live-announcements" />
    </div>
  )
}
