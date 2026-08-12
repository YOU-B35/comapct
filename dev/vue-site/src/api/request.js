/**
 * Axios：对接本项目 Java Temu API（/api/temu、/api/auth）
 */
import axios from 'axios'
import { getActivePinia } from 'pinia'
import router from '@/router'
import { TEMU_API_BASE_URL } from './config'

export const service = axios.create({
  baseURL: import.meta.env.DEV ? '' : TEMU_API_BASE_URL,
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

export function getAccessToken() {
  return localStorage.getItem('accessToken') || null
}

export function setAccessToken(token) {
  localStorage.setItem('accessToken', token)
}

export function clearAccessToken() {
  localStorage.removeItem('accessToken')
}

function clearSession() {
  clearAccessToken()
  localStorage.removeItem('crosshub_logged_in')
  try {
    if (getActivePinia()) {
      import('@/stores/auth').then(({ useAuthStore }) => {
        useAuthStore().logout()
      })
    }
  } catch (_) {
    /* ignore */
  }
}

import { getAppErrorMessage, formatUserMessage } from '@/utils/appErrorCode'

function pickMessage(data) {
  if (!data || typeof data !== 'object') return ''
  const code = String(data.error_code || '').trim()
  const msg = String(data.msg || data.message || '').trim()
  if (code) return getAppErrorMessage(code, msg)
  return msg
}

service.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

service.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res && typeof res === 'object' && 'code' in res && res.code !== 0 && res.code !== 200) {
      return Promise.reject(new Error(pickMessage(res) || '请求失败'))
    }
    return res
  },
  (error) => {
    const status = error.response?.status
    const errorCode = String(error.response?.data?.error_code || '').trim()
    let msg = pickMessage(error.response?.data) || formatUserMessage(error.message, '请求失败')
    const backendDown =
      !error.response
      || status === 502
      || status === 503
      || /ECONNREFUSED|Network Error|socket hang up/i.test(String(error.message || ''))
    if (backendDown && !errorCode) {
      msg = '后端服务未启动或不可用，请先启动 Java API（scripts\\restart-java-api.ps1）'
    }
    if (status === 401 && router.currentRoute.value?.path !== '/login') {
      clearSession()
      router.replace('/login')
    }
    const wrapped = new Error(msg)
    if (errorCode) wrapped.errorCode = errorCode
    if (error.response?.data?.data) wrapped.data = error.response.data.data
    return Promise.reject(wrapped)
  },
)

export async function backendLogin(account, password, portalRole) {
  const body = {
    account,
    password,
  }
  // portal_role 可选；后端按库内角色自动校准，前端传值仅兼容旧调用
  if (portalRole) {
    body.portal_role = portalRole
  }
  const res = await service.post('/api/auth/login', body)
  const data = res?.data ?? res
  const token = data?.token
  if (!token) throw new Error('登录失败：未返回 token')
  setAccessToken(token)
  return data
}

export async function fetchBackendSession() {
  const res = await service.get('/api/auth/session', { skipGlobalErrorToast: true })
  return res?.data ?? res
}
