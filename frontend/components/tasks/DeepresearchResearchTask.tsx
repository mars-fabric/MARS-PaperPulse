'use client'

import React, { useEffect, useCallback } from 'react'
import { ArrowLeft, Square, Trash2, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/core'
import Stepper from '@/components/core/Stepper'
import type { StepperStep } from '@/components/core/Stepper'
import { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import { DEEPRESEARCH_STEP_LABELS, WIZARD_STEP_TO_STAGE } from '@/types/deepresearch'
import type { DeepresearchWizardStep } from '@/types/deepresearch'
import SetupPanel from '@/components/deepresearch/SetupPanel'
import ReviewPanel from '@/components/deepresearch/ReviewPanel'
import ExecutionPanel from '@/components/deepresearch/ExecutionPanel'
import PaperPanel from '@/components/deepresearch/PaperPanel'

interface DeepresearchResearchTaskProps {
  onBack: () => void
  resumeTaskId?: string | null
}

export default function DeepresearchResearchTask({ onBack, resumeTaskId }: DeepresearchResearchTaskProps) {
  const hook = useDeepresearchTask()
  const {
    taskId,
    taskState,
    currentStep,
    isLoading,
    error,
    isExecuting,
    setCurrentStep,
    resumeTask,
    stopTask,
    deleteTask,
    clearError,
  } = hook

  // Resume on mount if resumeTaskId provided
  useEffect(() => {
    if (resumeTaskId) {
      resumeTask(resumeTaskId)
    }
  }, [resumeTaskId, resumeTask])

  // Build stepper steps from taskState
  const stepperSteps: StepperStep[] = DEEPRESEARCH_STEP_LABELS.map((label, idx) => {
    const stageNum = WIZARD_STEP_TO_STAGE[idx]
    let status: StepperStep['status'] = 'pending'

    if (idx === currentStep) {
      status = 'active'
    } else if (idx < currentStep) {
      status = 'completed'
    }

    // Override with real stage status if task exists
    if (taskState && stageNum) {
      const stage = taskState.stages.find(s => s.stage_number === stageNum)
      if (stage) {
        if (stage.status === 'completed') status = 'completed'
        else if (stage.status === 'failed') status = 'failed'
        else if (stage.status === 'running') status = 'active'
      }
    }

    // Step 0 (setup) is completed once task is created
    if (idx === 0 && taskId) {
      status = 'completed'
    }

    return { id: `step-${idx}`, label, status }
  })

  const goNext = useCallback(() => {
    if (currentStep < 4) {
      setCurrentStep((currentStep + 1) as DeepresearchWizardStep)
    }
  }, [currentStep, setCurrentStep])

  const goBack = useCallback(() => {
    if (currentStep > 0 && !isExecuting) {
      setCurrentStep((currentStep - 1) as DeepresearchWizardStep)
    }
  }, [currentStep, isExecuting, setCurrentStep])

  // Jump directly to a step by clicking its dot in the Stepper. We rely on the
  // Stepper itself to gate clicks to completed / active / failed steps; here
  // we additionally block navigation while a stage is executing so we don't
  // pull the rug from under a running run.
  const handleStepClick = useCallback((index: number) => {
    if (isExecuting) return
    if (index < 0 || index > 4) return
    setCurrentStep(index as DeepresearchWizardStep)
  }, [isExecuting, setCurrentStep])

  const handleStop = useCallback(async () => {
    await stopTask()
  }, [stopTask])

  const handleDelete = useCallback(async () => {
    if (!confirm('Delete this task? This will remove all data and files.')) return
    await deleteTask()
    onBack()
  }, [deleteTask, onBack])

  return (
    <div className="p-5 max-w-7xl mx-auto mars-anim-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={onBack}
          className="p-2 rounded-lg transition-all duration-150 hover:scale-105 active:scale-95"
          style={{
            color: 'var(--mars-color-text-secondary)',
            backgroundColor: 'var(--mars-color-surface-raised)',
            border: '1px solid var(--mars-color-border)',
          }}
          title="Back to home"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2
              className="text-xl font-bold tracking-tight truncate"
              style={{ color: 'var(--mars-color-text)' }}
            >
              {taskState?.task || 'New Research'}
            </h2>
            <span
              className="flex-shrink-0 text-[10px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded"
              style={{
                background: 'linear-gradient(135deg, rgba(139,92,246,0.20), rgba(99,102,241,0.20))',
                color: 'var(--mars-color-primary)',
                border: '1px solid rgba(139,92,246,0.35)',
              }}
            >
              Stage {currentStep + 1}/5
            </span>
          </div>
          <p
            className="text-xs mt-1"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            {DEEPRESEARCH_STEP_LABELS[currentStep]} · AI Research Paper Generation
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
        {(() => {
          const allDone =
            !!taskState &&
            taskState.stages.length > 0 &&
            taskState.stages.every(s => s.status === 'completed')
          return allDone ? (
            <div
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-semibold"
              style={{
                background: 'linear-gradient(135deg, rgba(34,197,94,0.18), rgba(22,163,74,0.10))',
                color: 'var(--mars-color-success)',
                border: '1px solid rgba(34,197,94,0.45)',
                boxShadow: '0 0 12px rgba(34,197,94,0.20)',
              }}
              title="All 4 stages completed"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Completed
            </div>
          ) : null
        })()}
        {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
          <div
            className="text-xs px-3 py-1.5 rounded-lg font-mono tabular-nums"
            style={{
              backgroundColor: 'var(--mars-color-surface-raised)',
              color: 'var(--mars-color-text-secondary)',
              border: '1px solid var(--mars-color-border)',
            }}
            title="Total cost so far"
          >
            <span style={{ color: 'var(--mars-color-text-tertiary)' }}>$</span>{taskState.total_cost_usd.toFixed(4)}
          </div>
        )}
        {/* Task actions */}
        {taskId && (
          <div className="flex items-center gap-2">
            {isExecuting && (
              <Button
                onClick={handleStop}
                variant="danger"
                size="sm"
              >
                <Square className="w-3.5 h-3.5 mr-1" />
                Stop
              </Button>
            )}
            <Button
              onClick={handleDelete}
              variant="danger"
              size="sm"
              disabled={isExecuting}
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              Delete
            </Button>
          </div>
        )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="mb-4 p-3 rounded-mars-md flex items-center justify-between text-sm"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            color: 'var(--mars-color-danger)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          <span>{error}</span>
          <button onClick={clearError} className="ml-2 font-medium underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Stepper */}
      <div
        className="mb-8 px-6 py-5 rounded-2xl border"
        style={{
          background: 'linear-gradient(180deg, var(--mars-color-surface-raised), var(--mars-color-surface))',
          borderColor: 'var(--mars-color-border)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04), 0 4px 16px -8px rgba(0,0,0,0.20)',
        }}
      >
        <Stepper
          steps={stepperSteps}
          orientation="horizontal"
          size="sm"
          onStepClick={handleStepClick}
        />
      </div>

      {/* Panel content */}
      <div>
        {currentStep === 0 && (
          <SetupPanel hook={hook} onNext={goNext} />
        )}
        {currentStep === 1 && (
          <ReviewPanel
            hook={hook}
            stageNum={1}
            stageName="Idea Generation"
            sharedKey="research_idea"
            onNext={goNext}
            onBack={goBack}
          />
        )}
        {currentStep === 2 && (
          <ReviewPanel
            hook={hook}
            stageNum={2}
            stageName="Method Development"
            sharedKey="methodology"
            onNext={goNext}
            onBack={goBack}
          />
        )}
        {currentStep === 3 && (
          <ExecutionPanel
            hook={hook}
            stageNum={3}
            stageName="Experiment Execution"
            onNext={goNext}
            onBack={goBack}
          />
        )}
        {currentStep === 4 && (
          <PaperPanel
            hook={hook}
            stageNum={4}
            onBack={goBack}
          />
        )}
      </div>
    </div>
  )
}
