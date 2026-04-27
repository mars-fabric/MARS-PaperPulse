'use client'

import React, { useEffect, useCallback, useState } from 'react'
import { ArrowLeft, ArrowRight, Play, Timer, DollarSign, Settings2 } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from './ExecutionProgress'
import StageAdvancedSettings from './StageAdvancedSettings'
import ArtifactBrowser from './ArtifactBrowser'
import type { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import type { DeepresearchStageConfig } from '@/types/deepresearch'

interface ExecutionPanelProps {
  hook: ReturnType<typeof useDeepresearchTask>
  stageNum: number
  stageName: string
  onNext: () => void
  onBack: () => void
}

export default function ExecutionPanel({
  hook,
  stageNum,
  stageName,
  onNext,
  onBack,
}: ExecutionPanelProps) {
  const {
    taskId,
    taskState,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
    fetchStageArtifacts,
    artifacts,
    artifactsTotalFiles,
    artifactsTotalBytes,
    taskConfig,
    setTaskConfig,
  } = hook

  const [elapsed, setElapsed] = useState(0)
  const [showSettings, setShowSettings] = useState(false)
  const [contentLoaded, setContentLoaded] = useState(false)

  const updateCfg = useCallback((patch: Partial<DeepresearchStageConfig>) => {
    setTaskConfig({ ...taskConfig, ...patch })
  }, [taskConfig, setTaskConfig])

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isCompleted = stage?.status === 'completed'
  const isFailed = stage?.status === 'failed'
  const isNotStarted = stage?.status === 'pending'

  // (stage is started manually via the Run button in the pre-execution UI)

  // Load stage content (and the artifact manifest) once the experiment
  // completes so the artifact browser has data to render.
  useEffect(() => {
    if (stageNum === 3 && isCompleted && !contentLoaded) {
      fetchStageContent(stageNum).then(() => setContentLoaded(true))
    }
  }, [stageNum, isCompleted, contentLoaded, fetchStageContent])

  // Auto-fire next stage on continue, mirroring ReviewPanel's behaviour so
  // the user lands on stage 4 already running rather than on the idle
  // "Generate Paper" button.
  const handleNext = useCallback(() => {
    const nextStageNum = stageNum + 1
    if (nextStageNum <= 4) {
      const nextStage = taskState?.stages.find(s => s.stage_number === nextStageNum)
      if (nextStage?.status === 'pending') {
        executeStage(nextStageNum)
      }
    }
    onNext()
  }, [stageNum, taskState, executeStage, onNext])

  // Timer — reset to 0 when execution starts, then tick every second
  useEffect(() => {
    if (!isExecuting) return
    setElapsed(0) // Reset on each new execution/retry
    const interval = setInterval(() => {
      setElapsed(prev => prev + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [isExecuting])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  // Pre-execution: stage not started — compact header with gear icon
  if (isNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-3">
        {/* Header bar */}
        <div className="flex items-center justify-between py-2">
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {stageName}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(s => !s)}
              title="Advanced settings"
              className="p-1.5 rounded-mars-sm transition-colors"
              style={{
                color: showSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
                backgroundColor: showSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent',
              }}
            >
              <Settings2 className="w-4 h-4" />
            </button>
            <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
              <Play className="w-3.5 h-3.5 mr-1.5" />
              Run {stageName}
            </Button>
          </div>
        </div>

        {/* Inline settings (hidden by default) */}
        {showSettings && (
          <div
            className="p-4 rounded-mars-md border space-y-4"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <StageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
          </div>
        )}

        <div className="flex justify-start pt-1">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Stats bar */}
      <div className="flex items-center gap-6">
        {(isExecuting || elapsed > 0) && (
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <Timer className="w-3.5 h-3.5" />
            {formatTime(elapsed)}
          </div>
        )}
        {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <DollarSign className="w-3.5 h-3.5" />
            ${taskState.total_cost_usd.toFixed(4)}
          </div>
        )}
      </div>

      {/* Execution output — collapse to a compact summary once we have
          completed and the artifact browser is taking the spotlight */}
      <ExecutionProgress
        consoleOutput={consoleOutput}
        isExecuting={isExecuting}
        stageName={stageName}
      />

      {/* Artifact browser — every file Stage 3 produced. Mounted only after
          the experiment has completed so the user can review outputs before
          firing Stage 4. */}
      {stageNum === 3 && isCompleted && taskId && (
        <ArtifactBrowser
          taskId={taskId}
          stageNum={3}
          manifest={artifacts}
          totalFiles={artifactsTotalFiles}
          totalBytes={artifactsTotalBytes}
          onRefresh={() => fetchStageArtifacts(3, true)}
        />
      )}

      {/* Error display */}
      {isFailed && stage?.error && (
        <div
          className="p-3 rounded-mars-md text-sm"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            color: 'var(--mars-color-danger)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          {stage.error}
        </div>
      )}

      {/* Retry button for failed stages */}
      {isFailed && (
        <div className="space-y-3">
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setShowSettings(s => !s)}
              title="Advanced settings"
              className="p-1.5 rounded-mars-sm transition-colors"
              style={{
                color: showSettings ? 'var(--mars-color-accent)' : 'var(--mars-color-text-secondary)',
                backgroundColor: showSettings ? 'var(--mars-color-accent-subtle, rgba(99,102,241,0.1))' : 'transparent',
              }}
            >
              <Settings2 className="w-4 h-4" />
            </button>
            <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
              <Play className="w-4 h-4 mr-1" />
              Retry
            </Button>
          </div>
          {showSettings && (
            <div
              className="p-4 rounded-mars-md border space-y-4"
              style={{ backgroundColor: 'var(--mars-color-surface-overlay)', borderColor: 'var(--mars-color-border)' }}
            >
              <StageAdvancedSettings stageNum={stageNum} cfg={taskConfig} updateCfg={updateCfg} />
            </div>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4">
        <Button
          onClick={onBack}
          variant="secondary"
          size="sm"
          disabled={isExecuting}
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <Button
          onClick={handleNext}
          variant="primary"
          size="sm"
          disabled={!isCompleted}
        >
          <Play className="w-3.5 h-3.5 mr-1.5" />
          Generate Paper
          <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  )
}
