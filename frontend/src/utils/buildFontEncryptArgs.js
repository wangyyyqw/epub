/**
 * Build CLI arguments for font encryption target selection.
 *
 * Mirrors the argument construction logic in EpubTools.vue's runTool method:
 *   if (selectedFontFamilies.length > 0) args.push('--target-font-families', ...selectedFontFamilies)
 *   if (selectedXhtmlFiles.length > 0) args.push('--target-xhtml-files', ...selectedXhtmlFiles)
 *
 * @param {string[]} fontFamilies - Selected font family names
 * @param {string[]} xhtmlFiles  - Selected XHTML file paths
 * @returns {string[]} CLI argument array fragment
 */
export function buildFontEncryptArgs(fontFamilies, xhtmlFiles) {
  const args = []
  if (fontFamilies.length > 0) {
    args.push('--target-font-families', ...fontFamilies)
  }
  if (xhtmlFiles.length > 0) {
    args.push('--target-xhtml-files', ...xhtmlFiles)
  }
  return args
}
