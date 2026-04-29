'use client'

import React, { useEffect, useCallback, useState } from 'react'
import { ArrowLeft, ArrowRight, Play, Timer, DollarSign, Settings2, ListChecks, Loader2 } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from './ExecutionProgress'
import StageAdvancedSettings from './StageAdvancedSettings'
import ArtifactBrowser from './ArtifactBrowser'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
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
    previewExperimentPlan,
  } = hook

  const [elapsed, setElapsed] = useState(0)
  const [showSettings, setShowSettings] = useState(false)
  const [contentLoaded, setContentLoaded] = useState(false)
  const [planLoading, setPlanLoading] = useState(false)
  const [planMarkdown, setPlanMarkdown] = useState<string | null>(null)
  const [planSources, setPlanSources] = useState<string[]>([])
  const [planError, setPlanError] = useState<string | null>(null)

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

  // Plan preview is only meaningful for the experiment stage (Stage 3).
  const supportsPlanPreview = stageNum === 3
  const handlePreviewPlan = useCallback(async () => {
    setPlanLoading(true)
    setPlanError(null)
    const resp = await previewExperimentPlan()
    setPlanLoading(false)
    if (resp) {
      setPlanMarkdown(resp.plan_markdown)
      setPlanSources(resp.based_on)
    } else {
      setPlanError('Could not generate plan. See console for details.')
    }
  }, [previewExperimentPlan])

  // Pre-execution: stage not started — modern hero card
  if (isNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-4 mars-anim-fade-in">
        {/* Hero card */}
        <div
          className="relative rounded-2xl border p-6 overflow-hidden"
          style={{
            background: 'linear-gradient(180deg, var(--mars-color-surface-raised), var(--mars-color-surface))',
            borderColor: 'var(--mars-color-border)',
            boxShadow: '0 4px 16px -8px rgba(0,0,0,0.20)',
          }}
        >
          {/* Soft accent glow in corner */}
          <div
            aria-hidden
            className="absolute -top-16 -right-16 w-48 h-48 rounded-full opacity-30 blur-3xl pointer-events-none"
            style={{ background: 'radial-gradient(circle, #8b5cf6, transparent 70%)' }}
          />
          <div className="relative flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center mars-glow"
                  style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
                >
                  <Play className="w-4 h-4 text-white" fill="white" />
                </div>
                <div>
                  <h3 className="text-base font-bold tracking-tight" style={{ color: 'var(--mars-color-text)' }}>
                    {stageName}
                  </h3>
                  <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                    Ready to run · streams output live
                  </p>
                </div>
              </div>
              <p className="text-sm mt-3" style={{ color: 'var(--mars-color-text-secondary)' }}>
                The agent will read your idea & methodology and execute the experiment.
                {supportsPlanPreview && (
                  <span> Use <span className="font-semibold" style={{ color: 'var(--mars-color-text)' }}>Preview plan</span> first to see what's about to run, no cost.</span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {supportsPlanPreview && (
                <button
                  onClick={handlePreviewPlan}
                  disabled={planLoading}
                  title="Generate a quick plan summary before committing to the full experiment run"
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all duration-150 hover:scale-[1.02] disabled:opacity-50"
                  style={{
                    backgroundColor: 'var(--mars-color-surface-overlay)',
                    color: 'var(--mars-color-text-secondary)',
                    border: '1px solid var(--mars-color-border)',
                  }}
                >
                  {planLoading
                    ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Planning…</>
                    : <><ListChecks className="w-3.5 h-3.5" />Preview plan</>}
                </button>
              )}
              <button
                onClick={() => setShowSettings(s => !s)}
                title="Advanced settings"
                className="p-2 rounded-lg transition-all duration-150 hover:scale-105"
                style={{
                  color: showSettings ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
                  backgroundColor: showSettings ? 'var(--mars-color-primary-subtle)' : 'var(--mars-color-surface-overlay)',
                  border: '1px solid var(--mars-color-border)',
                }}
              >
                <Settings2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => executeStage(stageNum)}
                className="mars-shimmer-btn inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all duration-200 hover:shadow-2xl hover:scale-[1.02] active:scale-[0.98]"
                style={{
                  background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                  boxShadow: '0 6px 22px rgba(99, 102, 241, 0.40), inset 0 1px 0 rgba(255,255,255,0.18)',
                }}
              >
                <Play className="w-3.5 h-3.5" fill="currentColor" />
                Run {stageName}
              </button>
            </div>
          </div>
        </div>

        {/* Plan preview (Stage 3 only) */}
        {supportsPlanPreview && (planMarkdown || planError) && (
          <div
            className="p-4 rounded-mars-md border"
            style={{
              backgroundColor: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold flex items-center gap-1.5" style={{ color: 'var(--mars-color-text)' }}>
                <ListChecks className="w-3.5 h-3.5" />
                Planned experiment steps
              </span>
              <button
                onClick={handlePreviewPlan}
                disabled={planLoading}
                className="text-xs font-medium"
                style={{ color: 'var(--mars-color-text-secondary)' }}
                title="Re-generate the plan preview"
              >
                {planLoading ? 'Re-planning…' : 'Re-plan'}
              </button>
            </div>
            {planError && (
              <p className="text-xs" style={{ color: 'var(--mars-color-danger)' }}>{planError}</p>
            )}
            {planSources.length > 0 && (
              <p className="text-[11px] mb-2" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                Based on: {planSources.join(', ')}
              </p>
            )}
            {planMarkdown && (
              <div className="text-xs">
                <MarkdownRenderer content={planMarkdown} />
              </div>
            )}
            <p className="text-[11px] mt-2" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              This is a cheap preview — no experiment is run. Click <span className="font-medium">Run {stageName}</span> when you're satisfied.
            </p>
          </div>
        )}

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
    <div className="max-w-4xl mx-auto space-y-4 mars-anim-fade-in">
      {/* Stats bar */}
      {(isExecuting || elapsed > 0 || (taskState?.total_cost_usd != null && taskState.total_cost_usd > 0)) && (
        <div className="flex items-center gap-2 flex-wrap">
          {(isExecuting || elapsed > 0) && (
            <div
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-mono tabular-nums"
              style={{
                backgroundColor: 'var(--mars-color-surface-raised)',
                color: 'var(--mars-color-text-secondary)',
                border: '1px solid var(--mars-color-border)',
              }}
            >
              <Timer className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-primary)' }} />
              {formatTime(elapsed)}
            </div>
          )}
          {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
            <div
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-mono tabular-nums"
              style={{
                backgroundColor: 'var(--mars-color-surface-raised)',
                color: 'var(--mars-color-text-secondary)',
                border: '1px solid var(--mars-color-border)',
              }}
            >
              <DollarSign className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-success)' }} />
              {taskState.total_cost_usd.toFixed(4)}
            </div>
          )}
        </div>
      )}

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
        <button
          onClick={handleNext}
          disabled={!isCompleted}
          className="mars-shimmer-btn inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all duration-200 hover:shadow-2xl hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          style={{
            background: !isCompleted
              ? 'var(--mars-color-bg-tertiary)'
              : 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            boxShadow: !isCompleted ? 'none' : '0 6px 22px rgba(99, 102, 241, 0.40), inset 0 1px 0 rgba(255,255,255,0.18)',
            color: !isCompleted ? 'var(--mars-color-text-tertiary)' : 'white',
          }}
        >
          <Play className="w-3.5 h-3.5" fill="currentColor" />
          Generate Paper
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
