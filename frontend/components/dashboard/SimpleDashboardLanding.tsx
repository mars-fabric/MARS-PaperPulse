'use client'

import { FileText, Upload, Sparkles } from 'lucide-react'

export default function SimpleDashboardLanding({ onNewSession }: { onNewSession: () => void }) {

  return (
    <div
      className="relative h-full w-full flex flex-col items-center justify-center px-4 py-8 overflow-hidden"
      style={{ backgroundColor: 'var(--mars-color-bg)' }}
    >
      {/* Ambient brand glow — theme-aware, sits above the token background */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `
            radial-gradient(900px 480px at 50% -10%, var(--mars-color-primary-subtle) 0%, transparent 55%),
            radial-gradient(700px 400px at 85% 110%, rgba(139, 92, 246, 0.10) 0%, transparent 50%)
          `,
        }}
      />

      <div className="relative max-w-md w-full space-y-8 text-center">
        {/* Icon */}
        <div className="flex justify-center mars-animate-scale-in">
          <div className="w-20 h-20 rounded-2xl flex items-center justify-center bg-brand-gradient shadow-glow">
            <Sparkles className="w-10 h-10 text-white" />
          </div>
        </div>

        {/* Title & Subtitle */}
        <div className="space-y-3 mars-animate-in mars-delay-1">
          <h1 className="text-4xl font-bold tracking-tight" style={{ color: 'var(--mars-color-text)' }}>
            Paper<span className="mars-gradient-text">Pulse</span>
          </h1>
          <p className="text-base leading-relaxed" style={{ color: 'var(--mars-color-text-secondary)' }}>
            Generate deep scientific research papers through AI-powered interactive stages
          </p>
        </div>

        {/* CTA Button */}
        <div className="mars-animate-in mars-delay-2">
          <button
            onClick={onNewSession}
            className="mars-focus-ring w-full py-3.5 rounded-mars-lg text-sm font-semibold text-white
              bg-brand-gradient shadow-glow-sm transition-all duration-mars-normal ease-mars
              hover:-translate-y-0.5 hover:shadow-glow active:translate-y-0"
          >
            <span className="flex items-center justify-center gap-2">
              <FileText className="w-4 h-4" />
              Start New Research
            </span>
          </button>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-3 gap-4 pt-8 mars-animate-in mars-delay-3">
          {[
            {
              icon: Upload,
              title: 'Upload Data',
              desc: 'CSV, PDF, Text files',
              color: '#22D3EE',
            },
            {
              icon: Sparkles,
              title: 'AI Stages',
              desc: '4-phase pipeline',
              color: '#8B5CF6',
            },
            {
              icon: FileText,
              title: 'LaTeX Paper',
              desc: 'Publication ready',
              color: '#22C55E',
            },
          ].map((feature, idx) => {
            const FeatureIcon = feature.icon
            return (
              <div
                key={idx}
                className="mars-card-interactive p-4 group"
              >
                <div className="flex flex-col items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-mars-md flex items-center justify-center transition-transform duration-mars-normal group-hover:scale-110"
                    style={{
                      backgroundColor: `${feature.color}1F`,
                    }}
                  >
                    <FeatureIcon className="w-5 h-5" style={{ color: feature.color }} />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold" style={{ color: 'var(--mars-color-text)' }}>
                      {feature.title}
                    </h3>
                    <p className="text-[10px] mt-1" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                      {feature.desc}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

