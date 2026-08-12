/**
 * 网络等待期间用时间曲线推进进度（避免卡在起始百分比）。
 * 约 expectedMs 趋近 ceiling，不会假到 100%。
 */
export function createWaitingProgress({
  onProgress,
  from = 5,
  ceiling = 92,
  expectedMs = 60_000,
  tickMs = 400,
} = {}) {
  let stopped = false
  const startedAt = Date.now()
  const report = (value) => {
    if (stopped) return
    const next = Math.max(from, Math.min(ceiling, Math.round(value)))
    onProgress?.(next)
  }
  report(from)
  const timer = setInterval(() => {
    if (stopped) return
    const t = (Date.now() - startedAt) / Math.max(1, expectedMs)
    const eased = 1 - Math.exp(-2.2 * Math.min(t, 4))
    report(from + (ceiling - from) * eased)
  }, tickMs)
  return () => {
    stopped = true
    clearInterval(timer)
  }
}
