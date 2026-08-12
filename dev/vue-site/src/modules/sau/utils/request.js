import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_BASE_URL } from '@sau/utils/apiBase'
import { clearSauAuth, getSauToken } from '@sau/utils/authStorage'

const request = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000,
})

const isAuthRoute = (url = '') => /\/auth\/(login|register|crosshub-exchange)(?:\?|$)/.test(url)

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
    ElMessage.error(message)
    return Promise.reject(new Error(message))
  },
  (error) => {
    const status = error.response?.status
    const rawData = error.response?.data
    const message =
      (typeof rawData === 'object' && rawData !== null
        ? rawData.msg || rawData.message
        : null) ||
      (typeof rawData === 'string' && /413|too large|Entity Too Large/i.test(rawData)
        ? '文件过大，超过服务器上传上限，请压缩后再试'
        : null)
    const requestUrl = error.config?.url || ''

    if (message) {
      ElMessage.error(message)
    } else if (!error.response) {
      ElMessage.error('网络连接失败，请确认可访问线上自媒体服务')
    } else {
      switch (status) {
        case 403:
          ElMessage.error('拒绝访问')
          break
        case 404:
          ElMessage.error('请求地址不存在')
          break
        case 413:
          ElMessage.error('文件过大，超过服务器上传上限，请压缩后再试')
          break
        case 500:
          ElMessage.error('服务器内部错误')
          break
        default:
          ElMessage.error('网络错误')
      }
    }

    if (status === 401 && !isAuthRoute(requestUrl)) {
      clearSauAuth()
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
    })
  },
}

export default request
