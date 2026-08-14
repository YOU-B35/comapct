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

const RETRY_HINT = '请稍后重试'
const BALANCE_HINT = '余额不足'

/**
 * 非业务/非配置类错误（上游故障、网关、超时、网络等）→ 统一友好提示。
 * 鉴权、违规、参数错误等仍透出原文，便于用户处理。
 */
export function humanizeAiImageError(message, fallback) {
  const raw = String(message || '').trim()
  const text = raw || String(fallback || '').trim()
  if (!text) return RETRY_HINT

  // 上游余额 / 额度不足
  if (
    /余额不足|额度不足|quota|insufficient(?:\s+\w+)*\s+(?:quota|balance|credit|fund)|billing|no\s+credit|out\s+of\s+credit|余额|credit\s+limit/i.test(
      text,
    )
  ) {
    return BALANCE_HINT
  }

  // 业务 / 配置类：保留原文
  if (
    /api\s*key|unauthorized|forbidden|鉴权|未配置|violation|content.?policy|违规|invalid|参数|prompt|model|size/i.test(
      text,
    )
  ) {
    return text
  }

  // 上游 / 网关 / 超时 / 网络等瞬时故障
  if (
    /upstream|failed to download|gateway|bad gateway|service unavailable|timed?\s*out|timeout|network|failed to fetch|econnreset|enotfound|econnrefused|temporarily unavailable|overloaded|502|503|504|internal server error|server error|请耐心/i.test(
      text,
    )
  ) {
    return RETRY_HINT
  }

  // 英文技术型报错（用户无法处理）一律改成重试提示
  if (/^[A-Za-z0-9][\w\s./:-]*$/.test(text) && /fail|error|request|upstream|proxy|retry/i.test(text)) {
    return RETRY_HINT
  }

  return text
}

function pickErrorMessage(data, fallback) {
  if (!data || typeof data !== 'object') return humanizeAiImageError('', fallback)
  const nested = data.error
  let msg = ''
  if (nested && typeof nested === 'object' && nested.message) msg = String(nested.message)
  else {
    msg =
      (typeof nested === 'string' ? nested : '')
      || data.message
      || data.msg
      || data.failure_reason
      || ''
  }
  return humanizeAiImageError(msg, fallback)
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
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw new Error(humanizeAiImageError(err?.message, RETRY_HINT))
  } finally {
    stopWaiting()
  }

  onProgress?.(94)
  const data = await readJson(res)
  if (!res.ok) {
    const fallback =
      res.status === 401 || res.status === 403
        ? '鉴权失败，请检查 API Key'
        : res.status === 402
          ? BALANCE_HINT
          : res.status === 400
            ? '请求参数有误'
            : res.status >= 500 || res.status === 429
              ? RETRY_HINT
              : `生图失败（HTTP ${res.status}）`
    throw new Error(pickErrorMessage(data, fallback))
  }
  const urls = extractUrlsFromOpenAi(data)
  if (!urls.length) {
    throw new Error(pickErrorMessage(data, RETRY_HINT))
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
