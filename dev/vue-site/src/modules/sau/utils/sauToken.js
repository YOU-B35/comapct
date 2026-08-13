/** Decode JWT exp when possible; opaque tokens are treated as usable until 401. */
export function isSauTokenUsable(token) {
  if (!token || typeof token !== 'string') return false
  const parts = token.split('.')
  if (parts.length < 2) return true
  try {
    const json = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const pad = json.length % 4 === 0 ? '' : '='.repeat(4 - (json.length % 4))
    const payload = JSON.parse(atob(json + pad))
    if (!payload?.exp) return true
    // Refresh 60s before expiry to avoid mid-request 401 races.
    return payload.exp * 1000 > Date.now() + 60_000
  } catch {
    return true
  }
}
