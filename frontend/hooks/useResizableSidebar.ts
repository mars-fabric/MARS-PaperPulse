'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

const STORAGE_KEY = 'mars-sidebar-width'
const MIN_WIDTH = 240
const MAX_WIDTH = 600
const DEFAULT_WIDTH = 280

export function useResizableSidebar() {
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Load width from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = parseInt(stored, 10)
      if (!isNaN(parsed) && parsed >= MIN_WIDTH && parsed <= MAX_WIDTH) {
        setWidth(parsed)
      }
    }
  }, [])

  // Save width to localStorage
  useEffect(() => {
    if (width >= MIN_WIDTH && width <= MAX_WIDTH) {
      localStorage.setItem(STORAGE_KEY, width.toString())
    }
  }, [width])

  // Handle mouse move for resizing
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing) return

    const container = containerRef.current
    if (!container) return

    const rect = container.getBoundingClientRect()
    const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, e.clientX - rect.left))
    setWidth(newWidth)
  }, [isResizing])

  // Handle mouse up to stop resizing
  const handleMouseUp = useCallback(() => {
    setIsResizing(false)
  }, [])

  // Attach global mouse event listeners
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove, { passive: true })
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'

      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
        document.body.style.userSelect = 'auto'
        document.body.style.cursor = 'auto'
      }
    }
  }, [isResizing, handleMouseMove, handleMouseUp])

  const startResizing = useCallback(() => {
    setIsResizing(true)
  }, [])

  return {
    width,
    isResizing,
    containerRef,
    startResizing,
    MIN_WIDTH,
    MAX_WIDTH,
  }
}
