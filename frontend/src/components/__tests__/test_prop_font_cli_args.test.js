// Feature: epub-tool-enhancements, Property 2: 字体加密 CLI 参数构建正确性
// Validates: Requirements 1.4

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { buildFontEncryptArgs } from '../../utils/buildFontEncryptArgs.js'

// Generators
const fontFamilyArb = fc.string({ minLength: 1, maxLength: 30 })
const xhtmlFileArb = fc.string({ minLength: 1, maxLength: 50 }).map(s => 'OEBPS/' + s + '.xhtml')

const fontFamiliesArb = fc.array(fontFamilyArb, { minLength: 0, maxLength: 10 })
const xhtmlFilesArb = fc.array(xhtmlFileArb, { minLength: 0, maxLength: 10 })

describe('Property 2: 字体加密 CLI 参数构建正确性', () => {
  it('should include --target-font-families flag followed by exact font families when non-empty', () => {
    fc.assert(
      fc.property(
        fc.array(fontFamilyArb, { minLength: 1, maxLength: 10 }),
        xhtmlFilesArb,
        (fontFamilies, xhtmlFiles) => {
          const args = buildFontEncryptArgs(fontFamilies, xhtmlFiles)
          const flagIndex = args.indexOf('--target-font-families')
          expect(flagIndex).toBe(0)

          // Values after the flag should be exactly the font families in order
          const endIndex = args.indexOf('--target-xhtml-files')
          const valuesEnd = endIndex === -1 ? args.length : endIndex
          const values = args.slice(flagIndex + 1, valuesEnd)
          expect(values).toEqual(fontFamilies)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should include --target-xhtml-files flag followed by exact xhtml files when non-empty', () => {
    fc.assert(
      fc.property(
        fontFamiliesArb,
        fc.array(xhtmlFileArb, { minLength: 1, maxLength: 10 }),
        (fontFamilies, xhtmlFiles) => {
          const args = buildFontEncryptArgs(fontFamilies, xhtmlFiles)
          const flagIndex = args.indexOf('--target-xhtml-files')
          expect(flagIndex).toBeGreaterThanOrEqual(0)

          // Values after the flag should be exactly the xhtml files in order
          const values = args.slice(flagIndex + 1)
          expect(values).toEqual(xhtmlFiles)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should omit --target-font-families when fontFamilies is empty', () => {
    fc.assert(
      fc.property(xhtmlFilesArb, (xhtmlFiles) => {
        const args = buildFontEncryptArgs([], xhtmlFiles)
        expect(args.includes('--target-font-families')).toBe(false)
      }),
      { numRuns: 100 }
    )
  })

  it('should omit --target-xhtml-files when xhtmlFiles is empty', () => {
    fc.assert(
      fc.property(fontFamiliesArb, (fontFamilies) => {
        const args = buildFontEncryptArgs(fontFamilies, [])
        expect(args.includes('--target-xhtml-files')).toBe(false)
      }),
      { numRuns: 100 }
    )
  })

  it('should return empty array when both inputs are empty', () => {
    const args = buildFontEncryptArgs([], [])
    expect(args).toEqual([])
  })

  it('should produce args whose total length equals flags + all values', () => {
    fc.assert(
      fc.property(fontFamiliesArb, xhtmlFilesArb, (fontFamilies, xhtmlFiles) => {
        const args = buildFontEncryptArgs(fontFamilies, xhtmlFiles)
        const expectedFlags = (fontFamilies.length > 0 ? 1 : 0) + (xhtmlFiles.length > 0 ? 1 : 0)
        const expectedLength = expectedFlags + fontFamilies.length + xhtmlFiles.length
        expect(args.length).toBe(expectedLength)
      }),
      { numRuns: 100 }
    )
  })
})
