/** Sync Helper 版本对比：用于提示/强制更新。 */

export function parseHelperVersion(version) {
  const text = String(version || '').trim()
  if (!text) return []
  return text
    .split('.')
    .map((part) => parseInt(part, 10))
    .filter((n) => Number.isFinite(n))
}

/** 本地版本为空或低于最新版 → 需要更新。 */
export function isHelperOutdated(localVersion, latestVersion) {
  const local = parseHelperVersion(localVersion)
  const latest = parseHelperVersion(latestVersion)
  if (!latest.length) return false // 无最新版本信息时不拦截
  if (!local.length) return true // 旧包未写版本号 → 视为过期
  const max = Math.max(local.length, latest.length)
  for (let i = 0; i < max; i += 1) {
    const a = local[i] || 0
    const b = latest[i] || 0
    if (a < b) return true
    if (a > b) return false
  }
  return false
}
