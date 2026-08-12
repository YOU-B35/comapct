const DEFAULT_SAU_API_BASE = 'https://automedia.yoto.work/api'

const rawBaseUrl = String(
  import.meta.env.VITE_SAU_API_BASE_URL ?? DEFAULT_SAU_API_BASE,
).trim()

function normalizeBaseUrl(baseUrl) {
  if (!baseUrl) return DEFAULT_SAU_API_BASE
  return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl
}

/**
 * SAU 业务 API 根地址（与线上 automedia 同契约）。
 * 默认直连 https://automedia.yoto.work/api，不经本机 Vite/5409 代理。
 */
export const API_BASE_URL = normalizeBaseUrl(rawBaseUrl)

export function buildApiUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}
