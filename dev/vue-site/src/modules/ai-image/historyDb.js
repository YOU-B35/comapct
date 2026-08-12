/**
 * 与原站 gpt-image-playground 同模式：浏览器 IndexedDB 持久化生图记录。
 * 原站：DB `gpt-image-playground` → stores tasks / images / thumbnails
 * 本站：DB `crosshub-ai-image` → stores results / images（避免与同域原站库结构冲突）
 */
const DB_NAME = 'crosshub-ai-image'
const DB_VERSION = 1
const STORE_RESULTS = 'results'
const STORE_IMAGES = 'images'
const MAX_RESULTS = 200

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(STORE_RESULTS)) {
        const store = db.createObjectStore(STORE_RESULTS, { keyPath: 'id' })
        store.createIndex('createdAt', 'createdAt', { unique: false })
      }
      if (!db.objectStoreNames.contains(STORE_IMAGES)) {
        db.createObjectStore(STORE_IMAGES, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error || new Error('IndexedDB open failed'))
  })
}

function withStore(storeName, mode, runner) {
  return openDb().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, mode)
        const store = tx.objectStore(storeName)
        let req
        try {
          req = runner(store)
        } catch (err) {
          reject(err)
          return
        }
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error || new Error('IndexedDB request failed'))
      }),
  )
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('图片本地缓存失败'))
    reader.readAsDataURL(blob)
  })
}

async function cacheRemoteImage(id, url) {
  if (!id || !url || !/^https?:\/\//i.test(url)) return null
  try {
    const res = await fetch(url)
    if (!res.ok) return null
    const blob = await res.blob()
    if (!blob || !blob.size) return null
    const dataUrl = await blobToDataUrl(blob)
    await withStore(STORE_IMAGES, 'readwrite', (store) =>
      store.put({
        id,
        dataUrl,
        sourceUrl: url,
        mime: blob.type || 'image/png',
        cachedAt: Date.now(),
      }),
    )
    return dataUrl
  } catch {
    return null
  }
}

export async function loadAiImageHistory() {
  if (typeof indexedDB === 'undefined') return []
  const rows = await withStore(STORE_RESULTS, 'readonly', (store) => store.getAll())
  const list = Array.isArray(rows) ? rows : []
  list.sort((a, b) => Number(b.createdAt || 0) - Number(a.createdAt || 0))

  const out = []
  for (const item of list) {
    const cached = await withStore(STORE_IMAGES, 'readonly', (store) => store.get(item.id)).catch(() => null)
    out.push({
      ...item,
      url: (cached && cached.dataUrl) || item.url,
      remoteUrl: item.remoteUrl || item.url,
      kind: item.kind || 'url',
    })
  }
  return out
}

export async function saveAiImageHistoryItem(item) {
  if (typeof indexedDB === 'undefined' || !item?.id) return item
  const remoteUrl = item.remoteUrl || item.url
  const record = {
    id: String(item.id),
    prompt: item.prompt || '',
    model: item.model || '',
    quality: item.quality || '',
    ratio: item.ratio || '',
    steps: item.steps ?? 'auto',
    count: item.count || 1,
    createdAt: item.createdAt || Date.now(),
    favorite: !!item.favorite,
    kind: item.kind || 'url',
    url: remoteUrl,
    remoteUrl,
  }
  await withStore(STORE_RESULTS, 'readwrite', (store) => store.put(record))

  // 后台缓存原图到 IndexedDB（与原站 images store 同思路），失败不影响列表
  cacheRemoteImage(record.id, remoteUrl).catch(() => {})

  await trimAiImageHistory()
  return record
}

export async function saveAiImageHistoryBatch(items = []) {
  const saved = []
  for (const item of items) {
    saved.push(await saveAiImageHistoryItem(item))
  }
  return saved
}

export async function deleteAiImageHistoryItem(id) {
  if (typeof indexedDB === 'undefined' || !id) return
  await withStore(STORE_RESULTS, 'readwrite', (store) => store.delete(String(id)))
  await withStore(STORE_IMAGES, 'readwrite', (store) => store.delete(String(id))).catch(() => {})
}

async function trimAiImageHistory() {
  const rows = await withStore(STORE_RESULTS, 'readonly', (store) => store.getAll())
  const list = Array.isArray(rows) ? rows : []
  if (list.length <= MAX_RESULTS) return
  list.sort((a, b) => Number(b.createdAt || 0) - Number(a.createdAt || 0))
  const drop = list.slice(MAX_RESULTS)
  for (const item of drop) {
    await deleteAiImageHistoryItem(item.id)
  }
}
