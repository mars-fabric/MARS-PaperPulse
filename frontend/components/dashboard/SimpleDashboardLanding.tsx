'use client'

import { FileText, Upload, Sparkles } from 'lucide-react'

export default function SimpleDashboardLanding({ onNewSession }: { onNewSession: () => void }) {

  return (
    <div
      className="h-full w-full flex flex-col items-center justify-center px-4 py-8"
      style={{
        background: `
          radial-gradient(1200px 600px at 20% 0%, rgba(99, 102, 241, 0.1) 0%, transparent 40%),
          linear-gradient(135deg, #0F172A 0%, #111827 50%, #0B1220 100%)
        `,
        minHeight: '100vh',
      }}
    >
      <div className="max-w-md w-full space-y-8 text-center">
        {/* Icon */}
        <div className="flex justify-center">
          <div
            className="w-20 h-20 rounded-2xl flex items-center justify-center shadow-lg"
            style={{
              background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
            }}
          >
            <Sparkles className="w-10 h-10 text-white" />
          </div>
        </div>

        {/* Title & Subtitle */}
        <div className="space-y-3">
          <h1 className="text-4xl font-bold" style={{ color: '#F9FAFB' }}>
            PaperPulse
          </h1>
          <p className="text-base leading-relaxed" style={{ color: 'rgba(156, 163, 175, 1)' }}>
            Generate deep scientific research papers through AI-powered interactive stages
          </p>
        </div>

        {/* CTA Button */}
        <button
          onClick={onNewSession}
          className="w-full py-3.5 rounded-lg text-sm font-semibold text-white transition-all duration-300 hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
          style={{
            background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
            boxShadow: '0 8px 24px rgba(99, 102, 241, 0.3)',
          }}
        >
          <span className="flex items-center justify-center gap-2">
            <FileText className="w-4 h-4" />
            Start New Research
          </span>
        </button>

        {/* Features Grid */}
        <div className="grid grid-cols-3 gap-4 pt-8">
          {[
            {
              icon: Upload,
              title: 'Upload Data',
              desc: 'CSV, PDF, Text files',
              color: '#00D4FF',
            },
            {
              icon: Sparkles,
              title: 'AI Stages',
              desc: '4-phase pipeline',
              color: '#8b5cf6',
            },
            {
              icon: FileText,
              title: 'LaTeX Paper',
              desc: 'Publication ready',
              color: '#51CF66',
            },
          ].map((feature, idx) => {
            const FeatureIcon = feature.icon
            return (
              <div
                key={idx}
                className="p-4 rounded-lg border transition-all hover:border-opacity-100"
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  borderColor: 'rgba(255, 255, 255, 0.1)',
                }}
              >
                <div className="flex flex-col items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{
                      backgroundColor: `${feature.color}20`,
                    }}
                  >
                    <FeatureIcon className="w-5 h-5" style={{ color: feature.color }} />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold" style={{ color: '#F9FAFB' }}>
                      {feature.title}
                    </h3>
                    <p className="text-[10px] mt-1" style={{ color: 'rgba(107, 114, 128, 1)' }}>
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
