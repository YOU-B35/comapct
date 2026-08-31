import axios from 'axios'
import { API_BASE_URL } from '@sau/utils/apiBase'
import { clearSauAuth, getSauToken } from '@sau/utils/authStorage'

const request = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Fail fast on hung automedia calls so nav/pages do not spin for minutes.
  timeout: 30000,
})

const isAuthRoute = (url = '') => /\/auth\/(login|register|crosshub-exchange)(?:\?|$)/.test(url)

let refreshInflight = null

function notifyError(message) {
  import('element-plus')
    .then(({ ElMessage }) => ElMessage.error(message))
    .catch(() => {
      if (import.meta.env.DEV) console.error(message)
    })
}

async function refreshSauAuthOnce() {
  if (!refreshInflight) {
    refreshInflight = import('@sau/utils/ensureSession')
      .then(({ ensureSauSession }) => ensureSauSession({ force: true }))
      .finally(() => {
        refreshInflight = null
      })
  }
  return refreshInflight
}

request.interceptors.request.use(
  (config) => {
    const token = getSauToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

request.interceptors.response.use(
  (response) => {
    const { data } = response

    if (data.code === 200 || data.success) {
      return data
    }

    const message = data.msg || data.message || '请求失败'
    notifyError(message)
    return Promise.reject(new Error(message))
  },
  async (error) => {
    const status = error.response?.status
    const config = error.config || {}
    const requestUrl = config.url || ''
    const rawData = error.response?.data

    // Expired/invalid SAU token: re-exchange once and retry the original call.
    if (status === 401 && !isAuthRoute(requestUrl) && !config.__sauRetried) {
      config.__sauRetried = true
      clearSauAuth()
      try {
        const { useSauUserStore } = await import('@sau/stores/user')
        useSauUserStore().logout()
      } catch {
        /* pinia may be unavailable in edge cases */
      }
      try {
        await refreshSauAuthOnce()
        const token = getSauToken()
        config.headers = config.headers || {}
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return request(config)
      } catch {
        // Fall through to normal error UI below.
      }
    }

    const message =
      (typeof rawData === 'object' && rawData !== null
        ? rawData.msg || rawData.message
        : null) ||
      (typeof rawData === 'string' && /413|too large|Entity Too Large/i.test(rawData)
        ? '文件过大，超过服务器上传上限，请压缩后再试'
        : null)

    if (message) {
      notifyError(message)
    } else if (!error.response) {
      notifyError('网络连接失败，请确认可访问线上自媒体服务')
    } else {
      switch (status) {
        case 401:
          notifyError('自媒体会话已失效，请刷新页面后重试')
          break
        case 403:
          notifyError('拒绝访问')
          break
        case 404:
          notifyError('请求地址不存在')
          break
        case 413:
          notifyError('文件过大，超过服务器上传上限，请压缩后再试')
          break
        case 500:
          notifyError('服务器内部错误')
          break
        default:
          notifyError('网络错误')
      }
    }

    if (status === 401 && !isAuthRoute(requestUrl)) {
      clearSauAuth()
      try {
        const { useSauUserStore } = await import('@sau/stores/user')
        useSauUserStore().logout()
      } catch {
        /* ignore */
      }
    }

    return Promise.reject(new Error(message || (status === 413 ? '文件过大' : '请求失败')))
  },
)

export const http = {
  get(url, params) {
    return request.get(url, { params })
  },

  post(url, data, config = {}) {
    return request.post(url, data, config)
  },

  put(url, data, config = {}) {
    return request.put(url, data, config)
  },

  delete(url, params) {
    return request.delete(url, { params })
  },

  upload(url, formData, onUploadProgress) {
    return request.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress,
      timeout: 300000,
    })
  },
}

export default request
