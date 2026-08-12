/**
 * AI 生图 API：同源 /api-proxy → hyhacct OpenAI 兼容通道（/v1/images/generations）
 */
import { loadAiImageSettings, resolveAiImageApiKey } from './settings'
import { createWaitingProgress } from './waitingProgress'

export { createWaitingProgress } from './waitingProgress'

function getProxyPrefix() {
  const settings = loadAiImageSettings()
  const raw = String(settings.apiUrl || '/api-proxy').trim() || '/api-proxy'
  // 仅允许同源相对路径，避免把 Key 打到任意外域
  if (raw.startsWith('/') && !raw.startsWith('//')) {
    return raw.replace(/\/+$/, '') || '/api-proxy'
  }
  return '/api-proxy'
}

function getApiKey() {
  return resolveAiImageApiKey()
}

function authHeaders(extra = {}) {
  const key = getApiKey()
  const headers = { Accept: 'application/json', ...extra }
  if (key) headers.Authorization = `Bearer ${key}`
  return headers
}

function pickErrorMessage(data, fallback) {
  if (!data || typeof data !== 'object') return fallback
  const nested = data.error
  if (nested && typeof nested === 'object' && nested.message) return String(nested.message)
  return (
    (typeof nested === 'string' ? nested : '')
    || data.message
    || data.msg
    || data.failure_reason
    || fallback
  )
}

async function readJson(res) {
  const text = await res.text()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}

function throwIfAborted(signal) {
  if (signal?.aborted) {
    const err = new Error('Aborted')
    err.name = 'AbortError'
    throw err
  }
}

async function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('参考图读取失败'))
    reader.readAsDataURL(file)
  })
}

/** UI 比例 / 旧 GRSAI 字面量 → OpenAI size */
function toOpenAiSize(sizeOrRatio) {
  const raw = String(sizeOrRatio || '1:1').trim()
  if (/^\d+x\d+$/i.test(raw)) return raw
  const map = {
    '1:1': '1024x1024',
    '3:2': '1536x1024',
    '2:3': '1024x1536',
    '4:3': '1536x1024',
    '3:4': '1024x1536',
    '16:9': '1536x1024',
    '9:16': '1024x1536',
  }
  return map[raw] || '1024x1024'
}

function extractUrlsFromOpenAi(payload) {
  const list = Array.isArray(payload?.data) ? payload.data : []
  return list
    .map((item) => {
      if (!item || typeof item !== 'object') return ''
      if (typeof item.url === 'string' && item.url.trim()) return item.url.trim()
      if (typeof item.b64_json === 'string' && item.b64_json.trim()) {
        return `data:image/png;base64,${item.b64_json.trim()}`
      }
      return ''
    })
    .filter(Boolean)
}

/** 上游仅提供 gpt-image-2-max；旧本地配置里的 gpt-image-2 必须改写 */
export function normalizeAiImageModel(model) {
  const raw = String(model || '').trim()
  if (!raw || raw === 'gpt-image-2' || /^gpt-image-2$/i.test(raw)) {
    return 'gpt-image-2-max'
  }
  return raw
}

/**
 * 提交一次 OpenAI 兼容生图
 */
async function runGenerateOnce({
  prompt,
  model,
  size,
  quality,
  images = [],
  signal,
  onProgress,
} = {}) {
  const body = {
    model: normalizeAiImageModel(model),
    prompt,
    n: 1,
    size: toOpenAiSize(size),
    response_format: 'url',
  }
  if (quality) body.quality = quality

  // 有参考图时走 images/edits（multipart）；无参考图走 generations
  const stopWaiting = createWaitingProgress({ onProgress, from: 5, ceiling: 92 })
  let res
  try {
    if (Array.isArray(images) && images.length) {
      const form = new FormData()
      form.append('model', body.model)
      form.append('prompt', String(prompt || ''))
      form.append('n', '1')
      form.append('size', body.size)
      if (quality) form.append('quality', quality)
      // data URL → Blob
      for (let i = 0; i < images.length; i += 1) {
        const dataUrl = images[i]
        const m = String(dataUrl).match(/^data:([^;]+);base64,(.+)$/)
        if (!m) continue
        const bin = atob(m[2])
        const bytes = new Uint8Array(bin.length)
        for (let j = 0; j < bin.length; j += 1) bytes[j] = bin.charCodeAt(j)
        const blob = new Blob([bytes], { type: m[1] || 'image/png' })
        form.append('image', blob, `ref-${i}.png`)
      }
      res = await fetch(`${getProxyPrefix()}/images/edits`, {
        method: 'POST',
        headers: authHeaders(),
        body: form,
        signal,
      })
    } else {
      res = await fetch(`${getProxyPrefix()}/images/generations`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal,
      })
    }
  } finally {
    stopWaiting()
  }

  onProgress?.(94)
  const data = await readJson(res)
  if (!res.ok) {
    throw new Error(pickErrorMessage(data, `生图失败（HTTP ${res.status}）`))
  }
  const urls = extractUrlsFromOpenAi(data)
  if (!urls.length) {
    throw new Error(pickErrorMessage(data, '生图成功但未返回图片地址'))
  }
  onProgress?.(100)
  return urls
}

/**
 * 文生图 / 图生图（参考图走 data URL）
 */
export async function produceAiImage({
  prompt,
  model,
  size,
  quality,
  n = 1,
  images = [],
  signal,
  onProgress,
} = {}) {
  const files = (images || []).filter((f) => f instanceof File)
  const dataUrls = []
  for (const file of files) {
    dataUrls.push(await fileToDataUrl(file))
  }

  const count = Math.max(1, Math.min(4, Number(n) || 1))
  const urls = []
  for (let i = 0; i < count; i += 1) {
    throwIfAborted(signal)
    const batchProgress = (p) => {
      const base = (i / count) * 100
      const span = 100 / count
      onProgress?.(Math.round(base + ((Number(p) || 0) * span) / 100))
    }
    const batch = await runGenerateOnce({
      prompt,
      model,
      size,
      quality,
      images: dataUrls,
      signal,
      onProgress: batchProgress,
    })
    urls.push(...batch)
  }

  if (!urls.length) throw new Error('接口未返回图片')
  onProgress?.(100)
  return urls.map((url, index) => ({
    id: `${Date.now()}-${index}`,
    url,
    kind: url.startsWith('data:') ? 'data-url' : 'url',
  }))
}

/** @deprecated 保留旧名 */
export async function generateImages(params) {
  return produceAiImage({ ...params, images: [] })
}

/** @deprecated 保留旧名 */
export async function editImages(params) {
  return produceAiImage(params)
}
