/** 项目内 Temu / CrossHub Java API 基址 */
function resolveTemuApiBaseUrl() {
  const raw = import.meta.env.VITE_TEMU_API_URL
  if (raw !== undefined && String(raw).trim() !== '') {
    return String(raw).trim().replace(/\/+$/, '')
  }
  // 生产同域部署（如 www.yoto.work/crosshub/）：走相对路径 /api/*
  if (import.meta.env.PROD) return ''
  return 'http://127.0.0.1:18080'
}

export const TEMU_API_BASE_URL = resolveTemuApiBaseUrl()

/** 默认走后端；仅当 VITE_USE_TEMU_BACKEND=false 时启用纯前端 Demo */
export function isTemuBackendEnabled() {
  const flag = import.meta.env.VITE_USE_TEMU_BACKEND
  if (flag === 'false' || flag === '0') return false
  return true
}
