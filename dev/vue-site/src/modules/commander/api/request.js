import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getAccessToken as getCrosshubAccessToken } from '@/api/request'

/** 开发走 Vite `/api/commander` → Java；生产同域 `/api/commander`（Nginx → Java BFF） */
export function getCommanderApiBase() {
  const fromEnv = String(import.meta.env.VITE_COMMANDER_API_BASE || '').trim()
  if (fromEnv) return fromEnv.replace(/\/$/, '')
  return ''
}

/** CrossHub JWT；不再使用独立 Commander token。 */
export function getAccessToken() {
  return getCrosshubAccessToken()
}

/** 上货任务 operator 字段：用 CrossHub 登录账号（无独立 Commander 用户名）。 */
export function getCommanderUsername() {
  try {
    const role = localStorage.getItem('crosshub_role') || ''
    const raw =
      role === 'employee'
        ? localStorage.getItem('crosshub_employee')
        : localStorage.getItem('crosshub_company')
    if (raw) {
      const obj = JSON.parse(raw)
      const account = String(obj?.account || obj?.username || obj?.name || '').trim()
      if (account) return account
    }
  } catch {
    /* ignore */
  }
  return ''
}

export function clearCommanderLocalState() {
  localStorage.removeItem('commander_accessToken')
  localStorage.removeItem('commander_isAuthenticated')
  localStorage.removeItem('commander_username')
}

export function isCommanderAuthenticated() {
  return Boolean(getAccessToken())
}

export const commanderService = axios.create({
  baseURL: getCommanderApiBase(),
  timeout: 300000,
})

commanderService.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

function pickMsg(data) {
  if (!data || typeof data !== 'object') return ''
  for (const k of ['msg', 'message', 'error', 'detail']) {
    if (data[k] != null && String(data[k]).trim()) return String(data[k]).trim()
  }
  return ''
}

function isBusinessSuccess(data) {
  if (data == null || typeof data !== 'object') return true
  if (!('code' in data) && !('status' in data)) return true
  const c = data.code != null ? data.code : data.status
  return c === 0 || c === 200 || c === '0' || c === '200'
}

let onUnauthorized = null
export function setCommanderUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

commanderService.interceptors.response.use(
  (response) => {
    const res = response.data
    if (response.config?.responseType === 'blob') return response
    if (res && (res.code === 401 || res.status === 401)) {
      onUnauthorized?.(pickMsg(res) || '登录已过期，请重新登录 CrossHub')
      return Promise.reject(new Error(pickMsg(res) || '登录已过期，请重新登录 CrossHub'))
    }
    if (!isBusinessSuccess(res)) {
      const msg = pickMsg(res) || '自动上货接口失败'
      if (!response.config?.skipGlobalErrorToast) ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }
    return res
  },
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      const msg = pickMsg(error.response?.data) || '登录已过期，请重新登录 CrossHub'
      onUnauthorized?.(msg)
      return Promise.reject(new Error(msg))
    }
    const msg =
      pickMsg(error.response?.data) ||
      error.message ||
      '自动上货网络错误'
    if (!error.config?.skipGlobalErrorToast) ElMessage.error(msg)
    return Promise.reject(new Error(msg))
  },
)
