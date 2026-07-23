'use client'

import React, { useState } from 'react'
import { Loader2 } from 'lucide-react'
import MacOSTerminalViewer from '../console/MacOSTerminalViewer'

interface ExecutionProgressProps {
  consoleOutput: string[]
  isExecuting: boolean
  stageName: string
  stageNumber?: number
}

export default function ExecutionProgress({
  consoleOutput,
  isExecuting,
  stageName,
  stageNumber = 0,
}: ExecutionProgressProps) {
  const [activeTab, setActiveTab] = useState('all')

  return (
    <div className="space-y-4">
      {/* Status indicator */}
      <div className="flex items-center gap-3">
        {isExecuting ? (
          <>
            <Loader2
              className="w-5 h-5 animate-spin"
              style={{ color: 'var(--mars-color-primary)' }}
            />
            <span
              className="text-sm font-medium"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Running {stageName}...
            </span>
          </>
        ) : (
          <span
            className="text-sm font-medium"
            style={{ color: 'var(--mars-color-success)' }}
          >
            ✓ {stageName} completed
          </span>
        )}
      </div>

      {/* macOS Terminal Viewer */}
      <MacOSTerminalViewer
        stageNumber={stageNumber}
        stageName={stageName}
        logs={consoleOutput}
        isExecuting={isExecuting}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        tabs={[
          { id: 'all', label: 'All output', count: consoleOutput.length },
          { id: 'planning', label: 'Planning & Control', count: Math.floor(consoleOutput.length / 2) },
        ]}
      />
    </div>
  )
}
