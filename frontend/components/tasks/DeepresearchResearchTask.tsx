'use client'

import React, { useEffect, useCallback } from 'react'
import { ArrowLeft, Square, Trash2 } from 'lucide-react'
import { Button } from '@/components/core'
import Stepper from '@/components/core/Stepper'
import type { StepperStep } from '@/components/core/Stepper'
import { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import { DEEPRESEARCH_STEP_LABELS, WIZARD_STEP_TO_STAGE } from '@/types/deepresearch'
import type { DeepresearchWizardStep } from '@/types/deepresearch'
import SetupPanel from '@/components/deepresearch/SetupPanel'
import ReviewPanel from '@/components/deepresearch/ReviewPanel'
import ExecutionPanel from '@/components/deepresearch/ExecutionPanel'
import ReportPanel from '@/components/deepresearch/ReportPanel'

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

  const handleStepClick = useCallback((stepIndex: number) => {
    // Allow clicking on completed or failed steps to navigate back
    // Prevent navigation if currently executing
    if (!isExecuting) {
      setCurrentStep(stepIndex as DeepresearchWizardStep)
    }
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
    <div className="p-5 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <button
          onClick={onBack}
          className="p-1.5 rounded-lg transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          title="Back to home"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h2
            className="text-lg font-semibold truncate"
            style={{ color: 'var(--mars-color-text)' }}
          >
            {taskState?.task || 'New Research'}
          </h2>
          <p
            className="text-xs mt-0.5"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Deep Scientific Research Paper Generation
          </p>
        </div>
        {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
          <div
            className="ml-auto text-xs px-3 py-1.5 rounded-mars-md"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              color: 'var(--mars-color-text-secondary)',
            }}
          >
            Cost: ${taskState.total_cost_usd.toFixed(4)}
          </div>
        )}
        {/* Task actions */}
        {taskId && (
          <div className={`flex items-center gap-2 ${taskState?.total_cost_usd ? '' : 'ml-auto'}`}>
            {isExecuting && (
              <Button
                onClick={handleStop}
                variant="secondary"
                size="sm"
              >
                <Square className="w-3.5 h-3.5 mr-1" />
                Stop
              </Button>
            )}
            <Button
              onClick={handleDelete}
              variant="secondary"
              size="sm"
              disabled={isExecuting}
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              Delete
            </Button>
          </div>
        )}
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
      <div className="mb-8">
        <Stepper steps={stepperSteps} orientation="horizontal" size="sm" onStepClick={handleStepClick} />
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
          <ReportPanel
            hook={hook}
            onBack={goBack}
          />
        )}
      </div>
    </div>
  )
}
