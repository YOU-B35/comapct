/**
 * Extract image File objects from a Clipboard paste event / clipboardData.
 */
export function collectImageFilesFromClipboard(clipboardData, maxCount = 10) {
  const limit = Math.max(1, Number(maxCount) || 10)
  const files = []
  const items = Array.from(clipboardData?.items || [])
  for (const item of items) {
    if (!item || item.kind !== 'file') continue
    if (!String(item.type || '').startsWith('image/')) continue
    const file = item.getAsFile?.()
    if (file) files.push(file)
  }
  if (files.length) {
    return files.slice(0, limit)
  }
  return Array.from(clipboardData?.files || [])
    .filter((f) => String(f?.type || '').startsWith('image/'))
    .slice(0, limit)
}
