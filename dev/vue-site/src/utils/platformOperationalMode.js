import { isTemuBackendEnabled } from '@/api/config'
import { getAccessToken } from '@/api/request'

/** Java 后端已提供运营读数的平台 */
const BACKEND_OPERATIONAL_PLATFORMS = new Set(['temu', 'aliexpress', 'amazon', 'douyin'])

export function isBackendOperationalSession() {
  if (!isTemuBackendEnabled()) return false
  if (!getAccessToken()) return false
  return localStorage.getItem('backend_linked') === '1'
}

/** 后端模式下该平台运营数据仍走 Demo/local */
export function isPlatformOperationalDemoOnly(platformKey) {
  if (!isBackendOperationalSession()) return false
  const key = String(platformKey || '').toLowerCase()
  return !BACKEND_OPERATIONAL_PLATFORMS.has(key)
}

export function platformOperationalHint(platformKey) {
  if (!isPlatformOperationalDemoOnly(platformKey)) return ''
  const key = String(platformKey || '').toLowerCase()
  if (key === 'aliexpress') {
    return ''
  }
  return '该平台运营数据接口开发中，当前仅展示账户绑定店铺。'
}
