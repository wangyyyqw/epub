// Feature: epub-merge-split, Property 1: 合并文件列表排序保持完整性
// Validates: Requirements 1.2, 1.4

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// Pure functions simulating merge file list operations

/**
 * Swap two items in array (simulates drag-and-drop reorder)
 */
function swapItems(list, fromIdx, toIdx) {
  const result = [...list]
  const item = result.splice(fromIdx, 1)[0]
  result.splice(toIdx, 0, item)
  return result
}

/**
 * Remove item at index
 */
function removeItem(list, index) {
  const result = [...list]
  result.splice(index, 1)
  return result
}

// Generators
const filePathArb = fc.string({ minLength: 1, maxLength: 60 }).map(s => '/path/to/' + s + '.epub')
const fileListArb = fc.array(filePathArb, { minLength: 1, maxLength: 20 })

describe('Property 1: 合并文件列表排序保持完整性', () => {
  it('swapItems preserves the same set of files and list length', () => {
    fc.assert(
      fc.property(
        fileListArb,
        fc.nat(),
        fc.nat(),
        (files, rawFrom, rawTo) => {
          const fromIdx = rawFrom % files.length
          const toIdx = rawTo % files.length
          const result = swapItems(files, fromIdx, toIdx)

          // Length unchanged
          expect(result.length).toBe(files.length)

          // Same multiset of elements
          expect([...result].sort()).toEqual([...files].sort())
        }
      ),
      { numRuns: 100 }
    )
  })

  it('removeItem decreases length by 1 and the removed file is no longer present', () => {
    fc.assert(
      fc.property(
        // Use unique file paths so we can assert absence after removal
        fc.array(filePathArb, { minLength: 1, maxLength: 20 }).chain(paths => {
          const unique = [...new Set(paths)]
          if (unique.length === 0) return fc.constant({ files: ['/path/to/fallback.epub'], index: 0 })
          return fc.nat({ max: unique.length - 1 }).map(idx => ({ files: unique, index: idx }))
        }),
        ({ files, index }) => {
          const removed = files[index]
          const result = removeItem(files, index)

          // Length decreases by 1
          expect(result.length).toBe(files.length - 1)

          // Removed file is no longer in the list
          expect(result).not.toContain(removed)
        }
      ),
      { numRuns: 100 }
    )
  })
})
