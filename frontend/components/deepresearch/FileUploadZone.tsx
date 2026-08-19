'use client'

import React, { useState, useCallback, useRef } from 'react'
import { Upload, X, FileIcon, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import type { UploadedFile } from '@/types/deepresearch'
import { MAX_UPLOAD_MB } from '@/lib/config'

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(1)} KB`
}

interface FileUploadZoneProps {
  files: UploadedFile[]
  onUpload: (file: File) => void
  disabled?: boolean
}

export default function FileUploadZone({ files, onUpload, disabled }: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled) setIsDragging(true)
  }, [disabled])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (disabled) return
    const droppedFiles = Array.from(e.dataTransfer.files)
    droppedFiles.forEach(onUpload)
  }, [disabled, onUpload])

  const handleClick = useCallback(() => {
    if (!disabled) inputRef.current?.click()
  }, [disabled])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || [])
    selected.forEach(onUpload)
    if (inputRef.current) inputRef.current.value = ''
  }, [onUpload])

  const statusIcon = (status: UploadedFile['status']) => {
    switch (status) {
      case 'uploading': return <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--mars-color-primary)' }} />
      case 'done': return <CheckCircle className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-success)' }} />
      case 'error': return <AlertCircle className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-danger)' }} />
      default: return <FileIcon className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-tertiary)' }} />
    }
  }

  return (
    <div>
      {/* Drop zone */}
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`group cursor-pointer rounded-mars-lg border-2 border-dashed p-8 text-center transition-all duration-mars-normal ${
          isDragging
            ? 'border-[var(--mars-color-primary)] bg-[var(--mars-color-primary-subtle)] scale-[1.01]'
            : 'border-[var(--mars-color-border-strong)] hover:border-[var(--mars-color-primary)] hover:bg-[var(--mars-color-bg-hover)]'
        }`}
        style={{ opacity: disabled ? 0.5 : 1 }}
      >
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-full flex items-center justify-center transition-transform duration-mars-normal group-hover:scale-110"
          style={{ backgroundColor: isDragging ? 'var(--mars-color-primary-subtle)' : 'var(--mars-color-surface-overlay)' }}
        >
          <Upload
            className="w-5 h-5"
            style={{ color: isDragging ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)' }}
          />
        </div>
        <p
          className="text-sm font-semibold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Drop files here or click to browse
        </p>
        <p
          className="text-xs mt-1"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          CSV, Excel, PDF, Word, JSON, TXT, and more (max {MAX_UPLOAD_MB}MB)
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleChange}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="px-3 py-2 rounded-mars-md text-xs border transition-colors"
              style={{
                backgroundColor: 'var(--mars-color-surface)',
                borderColor: f.status === 'error' ? 'var(--mars-color-danger)' : 'var(--mars-color-border)',
                color: 'var(--mars-color-text-secondary)',
              }}
            >
              <div className="flex items-center gap-2">
                {statusIcon(f.status)}
                <span className="flex-1 truncate font-medium" style={{ color: 'var(--mars-color-text)' }}>{f.name}</span>
                <span className="tabular-nums" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                  {formatSize(f.size)}
                </span>
              </div>
              {f.status === 'error' && f.error && (
                <p className="mt-1 pl-6" style={{ color: 'var(--mars-color-danger)' }}>{f.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
