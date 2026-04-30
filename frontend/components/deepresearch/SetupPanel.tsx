'use client'

import React, { useState, useCallback } from 'react'
import { Sparkles, Search, Settings2, Loader2 } from 'lucide-react'
import { Button } from '@/components/core'
import FileUploadZone from './FileUploadZone'
import FileContextPanel from './FileContextPanel'
import StageAdvancedSettings from './StageAdvancedSettings'
import type { useDeepresearchTask } from '@/hooks/useDeepresearchTask'
import type { DeepresearchStageConfig } from '@/types/deepresearch'

interface SetupPanelProps {
  hook: ReturnType<typeof useDeepresearchTask>
  onNext: () => void
}

export default function SetupPanel({ hook, onNext }: SetupPanelProps) {
  const {
    autoCreateTask,
    createTask,
    uploadFile,
    uploadedFiles,
    isLoading,
    executeStage,
    taskConfig,
    setTaskConfig,
    fileContextOutput,
    fileContextStatus,
    fileContext,
    analyzeFiles,
    refineFileContext,
    saveFileContext,
    setFileContext,
  } = hook

  const [description, setDescription] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const updateCfg = useCallback((patch: Partial<DeepresearchStageConfig>) => {
    setTaskConfig({ ...taskConfig, ...patch })
  }, [taskConfig, setTaskConfig])

  // Note: task is auto-created lazily on first file drop (inside uploadFile)
  // Do NOT call autoCreateTask here — it races with resumeTask on history resume

  const handleAnalyze = useCallback(async () => {
    setIsAnalyzing(true)
    await analyzeFiles()
    setIsAnalyzing(false)
  }, [analyzeFiles])

  const handleSubmit = useCallback(async () => {
    if (!description.trim()) return
    // createTask updates the description if task already exists, or creates fresh
    const id = await createTask(description, undefined)
    if (!id) return // creation failed — stay on this step, error is shown by hook
    await executeStage(1, id)
    onNext()
  }, [description, createTask, executeStage, onNext])

  const hasUploadedFiles = uploadedFiles.some(f => f.status === 'done')

  return (
    <div className="max-w-3xl mx-auto space-y-6 mars-anim-fade-in">

      {/* Research description */}
      <section className="mars-anim-slide-up">
        <div className="flex items-baseline justify-between mb-2">
          <label
            className="text-sm font-semibold flex items-center gap-2"
            style={{ color: 'var(--mars-color-text)' }}
          >
            <span
              className="inline-flex items-center justify-center w-5 h-5 rounded-md text-[10px] font-bold"
              style={{
                background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                color: 'white',
              }}
            >
              1
            </span>
            Research Description
          </label>
          <span className="text-[10px]" style={{ color: 'var(--mars-color-text-tertiary)' }}>
            {description.length} chars
          </span>
        </div>
        <div
          className="rounded-xl border transition-all duration-200 focus-within:border-[var(--mars-color-primary)] focus-within:shadow-[0_0_0_3px_rgba(139,92,246,0.15)]"
          style={{
            backgroundColor: 'var(--mars-color-surface-raised)',
            borderColor: 'var(--mars-color-border)',
          }}
        >
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe your research question, area of investigation, or the study you want to pursue…"
            rows={5}
            className="w-full bg-transparent rounded-xl p-3.5 text-sm resize-none outline-none"
            style={{ color: 'var(--mars-color-text)' }}
          />
        </div>
        <p
          className="text-xs mt-1.5"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          Be specific about your research goals. The AI will generate ideas based on this description and your uploaded data.
        </p>
      </section>

      {/* Research data files */}
      <section className="mars-anim-slide-up mars-delay-200">
        <label
          className="text-sm font-semibold flex items-center gap-2 mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          <span
            className="inline-flex items-center justify-center w-5 h-5 rounded-md text-[10px] font-bold"
            style={{
              background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
              color: 'white',
            }}
          >
            2
          </span>
          Research Data Files
          <span
            className="ml-1 text-[10px] font-normal px-1.5 py-0.5 rounded-full"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              color: 'var(--mars-color-text-tertiary)',
            }}
          >
            optional
          </span>
          <span
            className="ml-1 text-[11px] font-normal"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            CSV · FITS · HDF5 · JSON · NPY · PDF · TXT
          </span>
        </label>

        <FileUploadZone
          files={uploadedFiles}
          onUpload={uploadFile}
          disabled={isLoading}
        />

        {/* Understand My Data button */}
        {hasUploadedFiles && fileContextStatus === 'idle' && (
          <div className="mt-3 flex justify-end">
            <Button
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              variant="secondary"
              size="sm"
            >
              <Search className="w-3.5 h-3.5 mr-2" />
              Understand My Data
            </Button>
          </div>
        )}

        {/* Re-analyze button after done / error */}
        {hasUploadedFiles && (fileContextStatus === 'done' || fileContextStatus === 'error') && (
          <div className="mt-3 flex justify-end">
            <Button
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              variant="secondary"
              size="sm"
            >
              {isAnalyzing ? (
                <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />Re-analyzing...</>
              ) : (
                <><Search className="w-3.5 h-3.5 mr-2" />Re-analyze Files</>
              )}
            </Button>
          </div>
        )}

        {/* Streaming analysis + editable context panel */}
        {fileContextStatus !== 'idle' && (
          <div className="mt-3">
            <FileContextPanel
              fileContextOutput={fileContextOutput}
              fileContextStatus={fileContextStatus}
              fileContext={fileContext}
              onRefine={refineFileContext}
              onSave={saveFileContext}
              onContextChange={setFileContext}
            />
          </div>
        )}
      </section>

      {/* Stage 1 settings + submit */}
      <section className="space-y-3 mars-anim-slide-up mars-delay-300">
        {/* Settings row */}
        <div className="flex items-center justify-between">
          <span
            className="text-xs font-medium"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            Idea Generation settings
          </span>
          <button
            onClick={() => setShowSettings(s => !s)}
            title="Advanced settings for Idea Generation"
            className="p-1.5 rounded-lg transition-all duration-150 hover:scale-105"
            style={{
              color: showSettings ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
              backgroundColor: showSettings ? 'var(--mars-color-primary-subtle)' : 'transparent',
            }}
          >
            <Settings2 className="w-4 h-4" />
          </button>
        </div>

        {showSettings && (
          <div
            className="p-4 rounded-xl border"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <StageAdvancedSettings stageNum={1} cfg={taskConfig} updateCfg={updateCfg} />
          </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={!description.trim() || isLoading}
            className="mars-shimmer-btn inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 hover:shadow-2xl hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            style={{
              background: !description.trim() || isLoading
                ? 'var(--mars-color-bg-tertiary)'
                : 'linear-gradient(135deg, #8b5cf6, #6366f1)',
              boxShadow: !description.trim() || isLoading
                ? 'none'
                : '0 6px 22px rgba(99, 102, 241, 0.40), inset 0 1px 0 rgba(255,255,255,0.18)',
              color: !description.trim() || isLoading ? 'var(--mars-color-text-tertiary)' : 'white',
            }}
          >
            {isLoading ? (
              <><Loader2 className="w-4 h-4 animate-spin" />Generating…</>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Generate Ideas
                <span className="opacity-70">→</span>
              </>
            )}
          </button>
        </div>
      </section>

    </div>
  )
}

