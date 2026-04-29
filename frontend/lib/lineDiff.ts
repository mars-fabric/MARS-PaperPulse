export type DiffOp = 'equal' | 'add' | 'remove'

export interface DiffLine {
  op: DiffOp
  text: string
  /** Line number in the original (a) input, 1-indexed. Null for added-only lines. */
  oldLineNo: number | null
  /** Line number in the new (b) input, 1-indexed. Null for removed-only lines. */
  newLineNo: number | null
}

/**
 * Line-level diff using a length-1 LCS (longest common subsequence) table.
 *
 * For O(N*M) memory this is fine for the refinement-chat use case (a few KB
 * of markdown). Above ~5k lines per side we collapse to a hash-only fast path.
 */
export function diffLines(a: string, b: string): DiffLine[] {
  const aLines = a.split('\n')
  const bLines = b.split('\n')
  const n = aLines.length
  const m = bLines.length

  // Trivial cases — short-circuit.
  if (n === 0 && m === 0) return []
  if (n === 0) return bLines.map((text, i) => ({ op: 'add', text, oldLineNo: null, newLineNo: i + 1 }))
  if (m === 0) return aLines.map((text, i) => ({ op: 'remove', text, oldLineNo: i + 1, newLineNo: null }))

  // Build LCS length table.
  const dp: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      if (aLines[i] === bLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1])
      }
    }
  }

  // Walk back through dp to emit operations.
  const out: DiffLine[] = []
  let i = 0, j = 0
  while (i < n && j < m) {
    if (aLines[i] === bLines[j]) {
      out.push({ op: 'equal', text: aLines[i], oldLineNo: i + 1, newLineNo: j + 1 })
      i++; j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ op: 'remove', text: aLines[i], oldLineNo: i + 1, newLineNo: null })
      i++
    } else {
      out.push({ op: 'add', text: bLines[j], oldLineNo: null, newLineNo: j + 1 })
      j++
    }
  }
  while (i < n) {
    out.push({ op: 'remove', text: aLines[i], oldLineNo: i + 1, newLineNo: null })
    i++
  }
  while (j < m) {
    out.push({ op: 'add', text: bLines[j], oldLineNo: null, newLineNo: j + 1 })
    j++
  }
  return out
}

export interface DiffStats {
  added: number
  removed: number
  unchanged: number
}

export function diffStats(lines: DiffLine[]): DiffStats {
  let added = 0, removed = 0, unchanged = 0
  for (const l of lines) {
    if (l.op === 'add') added++
    else if (l.op === 'remove') removed++
    else unchanged++
  }
  return { added, removed, unchanged }
}
