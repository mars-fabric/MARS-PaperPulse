'use client'

import { useEffect, useMemo, useRef } from 'react'
// CSS-only side-effect import. Next.js bundles this into the global stylesheet
// (~24 KB, ~7 KB gzip) at build time. The heavy KaTeX *JavaScript* (~250 KB)
// is loaded lazily below via dynamic `import('katex')`.
import 'katex/dist/katex.min.css'

interface MarkdownRendererProps {
  content: string
}

/**
 * Lightweight Markdown renderer using regex transforms.
 *
 * Math segments (inline `$…$` / `\(…\)`, display `$$…$$` / `\[…\]`) are
 * extracted before markdown processing so subscripts and underscores don't
 * confuse the markdown regexes. They are emitted as placeholder spans on the
 * first paint (so the document is immediately readable) and upgraded to
 * KaTeX-rendered HTML by a `useEffect` that lazy-imports `katex`.
 *
 * KaTeX (~270 KB / 75 KB gzipped) therefore stays out of the initial bundle.
 *
 * Output is wrapped with `.mars-markdown` for styling via mars.css.
 */
export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const html = useMemo(() => renderMarkdown(content), [content])
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = ref.current
    if (!root) return
    const pending = root.querySelectorAll<HTMLElement>('.mars-math-pending')
    if (pending.length === 0) return

    let cancelled = false
    import('katex').then((mod) => {
      if (cancelled) return
      const katex: any = (mod as any).default ?? mod
      pending.forEach((el) => {
        const tex = el.getAttribute('data-tex') || ''
        const display = el.getAttribute('data-display') === '1'
        try {
          katex.render(tex, el, {
            displayMode: display,
            throwOnError: false,
            strict: 'ignore',
            output: 'html',
          })
          el.classList.remove('mars-math-pending')
        } catch {
          // Leave the raw fallback text in place
        }
      })
    }).catch(() => {
      // If the dynamic import itself fails (offline build, etc.), the pending
      // spans keep showing the raw `$…$` source — still readable.
    })

    return () => { cancelled = true }
  }, [html])

  return (
    <div
      ref={ref}
      className="mars-markdown px-4 py-3"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

// ── Math protection ────────────────────────────────────────────────────────
// Math is extracted before markdown processing so the markdown regexes don't
// chew it up (e.g. underscores in subscripts being read as italics).

interface MathSegment {
  display: boolean
  tex: string
}

const MATH_PLACEHOLDER_PREFIX = ' MARSMATH'
const MATH_PLACEHOLDER_SUFFIX = ' '

function extractMath(src: string): { text: string; segments: MathSegment[] } {
  const segments: MathSegment[] = []
  let out = ''
  let i = 0
  const push = (display: boolean, tex: string) => {
    const idx = segments.length
    segments.push({ display, tex })
    out += `${MATH_PLACEHOLDER_PREFIX}${idx}${MATH_PLACEHOLDER_SUFFIX}`
  }
  while (i < src.length) {
    // Skip fenced code blocks verbatim
    if (src.startsWith('```', i)) {
      const end = src.indexOf('```', i + 3)
      if (end < 0) { out += src.slice(i); break }
      out += src.slice(i, end + 3)
      i = end + 3
      continue
    }
    // Skip inline code verbatim
    if (src[i] === '`') {
      const end = src.indexOf('`', i + 1)
      if (end < 0) { out += src.slice(i); break }
      out += src.slice(i, end + 1)
      i = end + 1
      continue
    }
    // Display math: $$ … $$
    if (src.startsWith('$$', i)) {
      const end = src.indexOf('$$', i + 2)
      if (end < 0) { out += src.slice(i); break }
      push(true, src.slice(i + 2, end).trim())
      i = end + 2
      continue
    }
    // Display math: \[ … \]
    if (src.startsWith('\\[', i)) {
      const end = src.indexOf('\\]', i + 2)
      if (end < 0) { out += src.slice(i); break }
      push(true, src.slice(i + 2, end).trim())
      i = end + 2
      continue
    }
    // Inline math: \( … \)
    if (src.startsWith('\\(', i)) {
      const end = src.indexOf('\\)', i + 2)
      if (end < 0) { out += src.slice(i); break }
      push(false, src.slice(i + 2, end).trim())
      i = end + 2
      continue
    }
    // Inline math: $ … $ (single-dollar) — must not be escaped, must contain
    // at least one non-space char, and must not be a price like "$5".
    if (src[i] === '$' && src[i - 1] !== '\\' && src[i - 1] !== '$') {
      // Find a matching $ that's not escaped, on the same paragraph
      let j = i + 1
      while (j < src.length && src[j] !== '\n') {
        if (src[j] === '$' && src[j - 1] !== '\\') break
        j++
      }
      if (j < src.length && src[j] === '$' && j > i + 1) {
        const inner = src.slice(i + 1, j)
        // Reject "$5" / "$5.99" / "USD$"-like fragments — require some math content
        if (/[\\^_=+\-*/<>{}()\[\]a-zA-Z]/.test(inner) && inner.trim().length > 0) {
          push(false, inner)
          i = j + 1
          continue
        }
      }
    }
    out += src[i]
    i++
  }
  return { text: out, segments }
}

function renderMathPlaceholder(seg: MathSegment): string {
  const sigil = seg.display ? '$$' : '$'
  const tex = escapeHtml(seg.tex)
  const display = seg.display ? '1' : '0'
  // The textual fallback inside the span is shown until the lazy KaTeX
  // module finishes loading, so users see the raw TeX rather than nothing.
  return (
    `<span class="mars-math-pending" data-tex="${tex}" data-display="${display}">` +
    `${escapeHtml(sigil + seg.tex + sigil)}` +
    `</span>`
  )
}

function injectMath(html: string, segments: MathSegment[]): string {
  if (segments.length === 0) return html
  // Collapse any <p>…display-math-only…</p> wrappers since <div> can't sit
  // inside a <p> per HTML spec (browsers auto-close it, breaking layout).
  const wrapRe = new RegExp(
    `<p>\\s*${MATH_PLACEHOLDER_PREFIX}(\\d+)${MATH_PLACEHOLDER_SUFFIX}\\s*</p>`,
    'g',
  )
  let out = html.replace(wrapRe, (_m, idx) => {
    const seg = segments[parseInt(idx, 10)]
    if (!seg) return ''
    return seg.display
      ? `<div class="mars-math-display">${renderMathPlaceholder(seg)}</div>`
      : renderMathPlaceholder(seg)
  })
  // Replace remaining inline placeholders.
  const re = new RegExp(`${MATH_PLACEHOLDER_PREFIX}(\\d+)${MATH_PLACEHOLDER_SUFFIX}`, 'g')
  out = out.replace(re, (_m, idx) => {
    const seg = segments[parseInt(idx, 10)]
    if (!seg) return ''
    const ph = renderMathPlaceholder(seg)
    return seg.display
      ? `<div class="mars-math-display">${ph}</div>`
      : ph
  })
  return out
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderMarkdown(md: string): string {
  // Extract math first so markdown regexes don't munge it.
  const { text: protectedSrc, segments } = extractMath(md)
  let html = ''
  const lines = protectedSrc.split('\n')
  let inCodeBlock = false
  let codeBlockContent = ''
  let codeBlockLang = ''
  let inList: 'ul' | 'ol' | null = null

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Code blocks
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        html += `<pre><code>${escapeHtml(codeBlockContent.trimEnd())}</code></pre>\n`
        codeBlockContent = ''
        inCodeBlock = false
      } else {
        if (inList) { html += inList === 'ul' ? '</ul>' : '</ol>'; inList = null }
        codeBlockLang = line.slice(3).trim()
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      codeBlockContent += line + '\n'
      continue
    }

    // Close lists if needed
    const isListItem = line.match(/^(\s*[-*]|\s*\d+\.)\s/)
    if (!isListItem && inList) {
      html += inList === 'ul' ? '</ul>\n' : '</ol>\n'
      inList = null
    }

    // Blank line
    if (line.trim() === '') {
      if (inList) { html += inList === 'ul' ? '</ul>\n' : '</ol>\n'; inList = null }
      continue
    }

    // Headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      html += `<h${level}>${inlineMarkdown(headingMatch[2])}</h${level}>\n`
      continue
    }

    // Horizontal rules
    if (line.match(/^(-{3,}|_{3,}|\*{3,})$/)) {
      html += '<hr>\n'
      continue
    }

    // Blockquotes
    if (line.startsWith('> ')) {
      html += `<blockquote><p>${inlineMarkdown(line.slice(2))}</p></blockquote>\n`
      continue
    }

    // Unordered list items
    const ulMatch = line.match(/^\s*[-*]\s+(.+)$/)
    if (ulMatch) {
      if (inList !== 'ul') {
        if (inList) html += '</ol>\n'
        html += '<ul>\n'
        inList = 'ul'
      }
      html += `  <li>${inlineMarkdown(ulMatch[1])}</li>\n`
      continue
    }

    // Ordered list items
    const olMatch = line.match(/^\s*\d+\.\s+(.+)$/)
    if (olMatch) {
      if (inList !== 'ol') {
        if (inList) html += '</ul>\n'
        html += '<ol>\n'
        inList = 'ol'
      }
      html += `  <li>${inlineMarkdown(olMatch[1])}</li>\n`
      continue
    }

    // Paragraph
    html += `<p>${inlineMarkdown(line)}</p>\n`
  }

  // Close any open blocks
  if (inCodeBlock) {
    html += `<pre><code>${escapeHtml(codeBlockContent.trimEnd())}</code></pre>\n`
  }
  if (inList) {
    html += inList === 'ul' ? '</ul>\n' : '</ol>\n'
  }

  return injectMath(html, segments)
}

function inlineMarkdown(text: string): string {
  let result = escapeHtml(text)
  // Bold
  result = result.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  result = result.replace(/__(.+?)__/g, '<strong>$1</strong>')
  // Italic
  result = result.replace(/\*(.+?)\*/g, '<em>$1</em>')
  result = result.replace(/_(.+?)_/g, '<em>$1</em>')
  // Inline code
  result = result.replace(/`(.+?)`/g, '<code>$1</code>')
  // Links [text](url)
  result = result.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  return result
}
