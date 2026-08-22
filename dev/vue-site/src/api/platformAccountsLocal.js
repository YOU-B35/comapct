import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { ensureAliexpressDemoData } from './aliexpressDemoLocal'
import { ensureAmazonDailyData } from './amazonDailyLocal'
import { ensureDtcDemoData } from './dtcDemoLocal'
import { isDtcPlatform } from '@/constants/platforms'
import { loadScoped, resolveTenantId, saveScoped, isDemoTemplateEnabled } from '@/utils/tenantStorage'

const STORAGE_KEY = 'crosshub_platform_accounts'
const REMOVED_DEMO_IDS_KEY = 'crosshub_removed_demo_store_ids'

const ALLOWED_PLATFORMS = ['temu', 'aliexpress', '1688', 'amazon', 'walmart', 'pdd', 'douyin', 'channels', 'shopify', 'wordpress']

const DEMO_STORES = [
  {
    id: 'demo_temu_1',
    platform: 'temu',
    storeName: '亿拓 Temu 美国店',
    account: 'temu.us@yituo-outdoor.com',
    password: 'Temu@Demo123',
    boundAt: '2026-06-20 09:15:00',
  },
  {
    id: 'demo_temu_2',
    platform: 'temu',
    storeName: '亿拓 Temu 欧洲店',
    account: 'temu.eu@yituo-outdoor.com',
    password: 'Temu@Demo456',
    boundAt: '2026-06-21 10:30:00',
  },
  {
    id: 'demo_aliexpress_1',
    platform: 'aliexpress',
    storeName: '亿拓速卖通旗舰店',
    account: 'aliexpress@yituo-outdoor.com',
    password: 'Ali@Demo123',
    boundAt: '2026-06-22 14:20:00',
  },
  {
    id: 'demo_aliexpress_2',
    platform: 'aliexpress',
    storeName: '亿拓速卖通户外专区',
    account: 'aliexpress.outdoor@yituo-outdoor.com',
    password: 'Ali@Demo456',
    boundAt: '2026-06-23 16:00:00',
  },
  {
    id: 'demo_1688_1',
    platform: '1688',
    storeName: '亿拓 1688 主采购号',
    account: '1688.main@yituo-outdoor.com',
    password: '1688@Demo123',
    boundAt: '2026-06-22 11:00:00',
  },
  {
    id: 'demo_1688_2',
    platform: '1688',
    storeName: '亿拓 1688 辅料采购号',
    account: '1688.accessory@yituo-outdoor.com',
    password: '1688@Demo456',
    boundAt: '2026-06-23 13:30:00',
  },
  {
    id: 'demo_amazon_1',
    platform: 'amazon',
    storeName: '亿拓 Amazon 美国站',
    account: 'amazon.us@yituo-outdoor.com',
    password: 'Amazon@Demo123',
    boundAt: '2026-06-22 15:00:00',
  },
  {
    id: 'demo_amazon_2',
    platform: 'amazon',
    storeName: '亿拓 Amazon 欧洲站',
    account: 'amazon.eu@yituo-outdoor.com',
    password: 'Amazon@Demo456',
    boundAt: '2026-06-23 17:30:00',
  },
  {
    id: 'demo_walmart_1',
    platform: 'walmart',
    storeName: '亿拓 Walmart 美国店',
    account: 'walmart.us@yituo-outdoor.com',
    password: 'Walmart@Demo123',
    boundAt: '2026-06-24 09:00:00',
  },
  {
    id: 'demo_walmart_2',
    platform: 'walmart',
    storeName: '亿拓 Walmart 加拿大店',
    account: 'walmart.ca@yituo-outdoor.com',
    password: 'Walmart@Demo456',
    boundAt: '2026-06-24 11:30:00',
  },
  {
    id: 'demo_pdd_1',
    platform: 'pdd',
    storeName: '亿拓户外拼多多旗舰店',
    account: 'pdd@yituo-outdoor.com',
    password: 'Pdd@Demo123',
    boundAt: '2026-06-24 13:00:00',
  },
  {
    id: 'demo_pdd_2',
    platform: 'pdd',
    storeName: '亿拓拼多多露营专区',
    account: 'pdd.outdoor@yituo-outdoor.com',
    password: 'Pdd@Demo456',
    boundAt: '2026-06-24 14:30:00',
  },
  {
    id: 'demo_douyin_1',
    platform: 'douyin',
    storeName: '亿拓户外抖音小店',
    account: 'douyin@yituo-outdoor.com',
    password: 'Douyin@Demo123',
    boundAt: '2026-06-24 15:00:00',
  },
  {
    id: 'demo_douyin_2',
    platform: 'douyin',
    storeName: '亿拓抖音直播号',
    account: 'douyin.live@yituo-outdoor.com',
    password: 'Douyin@Demo456',
    boundAt: '2026-06-24 16:00:00',
  },
  {
    id: 'demo_channels_1',
    platform: 'channels',
    storeName: '亿拓户外视频号',
    account: 'channels@yituo-outdoor.com',
    password: 'Channels@Demo123',
    boundAt: '2026-06-24 17:00:00',
  },
  {
    id: 'demo_channels_2',
    platform: 'channels',
    storeName: '亿拓视频号露营号',
    account: 'channels.camp@yituo-outdoor.com',
    password: 'Channels@Demo456',
    boundAt: '2026-06-24 18:00:00',
  },
  {
    id: 'demo_shopify_1',
    platform: 'shopify',
    storeName: '亿拓户外官网',
    account: 'admin@yituo-outdoor.com',
    password: 'Shopify@Demo123',
    boundAt: '2026-06-20 11:00:00',
  },
  {
    id: 'demo_shopify_2',
    platform: 'shopify',
    storeName: '亿拓欧洲站',
    account: 'eu-admin@yituo-outdoor.com',
    password: 'Shopify@Demo456',
    boundAt: '2026-06-21 15:30:00',
  },
  {
    id: 'demo_wordpress_1',
    platform: 'wordpress',
    storeName: '亿拓户外内容站',
    account: 'editor@yituo-outdoor.com',
    password: 'WP@Demo123',
    boundAt: '2026-06-22 09:45:00',
  },
]

function normalizePlatform(platform) {
  return String(platform || '').trim().toLowerCase()
}

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, []) || []
}

function saveAll(stores, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, stores)
}

function createId() {
  return `local_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

function loadRemovedDemoIds(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, REMOVED_DEMO_IDS_KEY, []) || []
}

function markDemoStoreRemoved(id, tenantId = resolveTenantId()) {
  const removed = loadRemovedDemoIds(tenantId)
  if (!removed.includes(id)) {
    saveScoped(tenantId, REMOVED_DEMO_IDS_KEY, [...removed, id])
  }
}

/** 初始化 Demo 店铺；用户主动解除的 Demo 店铺不会再次写入 */
export function ensureDemoStores(tenantId = resolveTenantId()) {
  if (!isDemoTemplateEnabled(tenantId)) return
  const existing = loadAll(tenantId)
  const removedIds = new Set(loadRemovedDemoIds(tenantId))
  const demoById = Object.fromEntries(DEMO_STORES.map((s) => [s.id, s]))
  const custom = existing.filter((s) => !demoById[s.id])
  const activeDemos = DEMO_STORES.filter((s) => !removedIds.has(s.id)).map((s) => {
    const current = existing.find((row) => row.id === s.id)
    return current ? { ...current } : { ...s }
  })
  saveAll([...custom, ...activeDemos], tenantId)
}

function validateStoreInput({ platform, storeName, account, password, id, stores }) {
  const p = normalizePlatform(platform)
  if (!ALLOWED_PLATFORMS.includes(p)) {
    return { error: '不支持的平台' }
  }

  const name = String(storeName || '').trim()
  const acc = String(account || '').trim()
  const pwd = String(password || '')

  if (!name) return { error: '店铺名称不能为空' }
  if (!acc) return { error: '登录账号不能为空' }
  if (!id && !pwd) return { error: '登录密码不能为空' }

  const duplicate = stores.find(
    (s) => s.platform === p && s.storeName === name && s.id !== id,
  )
  if (duplicate) {
    return { error: `该平台下已存在名为「${name}」的店铺` }
  }

  return { platform: p, storeName: name, account: acc, password: pwd }
}

function upsertLocalStore(stores, payload) {
  const { id, companyName } = payload
  const validation = validateStoreInput({ ...payload, stores })
  if (validation.error) return { error: validation.error }

  const boundAt = nowUtc8String()

  if (id) {
    const index = stores.findIndex((s) => s.id === id)
    if (index === -1) return { error: '店铺不存在' }
    const existing = stores[index]
    if (normalizePlatform(existing.platform) !== validation.platform) {
      return { error: '不允许修改店铺所属平台' }
    }
    stores[index] = {
      ...existing,
      storeName: validation.storeName,
      account: validation.account,
      password: validation.password || existing.password,
      companyName,
      boundAt,
    }
    return { data: { ...stores[index] } }
  }

  const row = {
    id: createId(),
    platform: validation.platform,
    storeName: validation.storeName,
    account: validation.account,
    password: validation.password,
    companyName,
    boundAt,
  }
  stores.push(row)
  return { data: { ...row } }
}

function syncOperationalDemoStores(stores) {
  const dtcStores = stores.filter((store) => isDtcPlatform(store.platform))
  ensureDtcDemoData(dtcStores)

  const aliexpressStores = stores.filter((store) => store.platform === 'aliexpress')
  ensureAliexpressDemoData(aliexpressStores)

  const amazonStores = stores.filter((store) => store.platform === 'amazon')
  ensureAmazonDailyData(amazonStores)
}

export function fetchLocalPlatformStores(platform) {
  ensureDemoStores()
  const p = normalizePlatform(platform)
  let data = loadAll()
  if (p && ALLOWED_PLATFORMS.includes(p)) {
    data = data.filter((s) => s.platform === p)
  }
  return { success: true, data }
}

export function bindLocalPlatformStoresBatch({ companyName, stores: items }) {
  ensureDemoStores()
  const stores = loadAll()
  const results = []
  const errors = []

  for (const item of items) {
    const result = upsertLocalStore(stores, { ...item, companyName })
    if (result.error) {
      errors.push({ storeName: item.storeName, platform: item.platform, message: result.error })
    } else {
      results.push(result.data)
    }
  }

  if (!results.length) {
    throw new Error(errors[0]?.message || '绑定失败')
  }

  saveAll(stores)
  syncOperationalDemoStores(stores)
  return {
    success: true,
    message: `成功绑定/更新 ${results.length} 个店铺`,
    data: results,
    errors: errors.length ? errors : undefined,
  }
}

export function deleteLocalPlatformStore(id) {
  ensureDemoStores()
  const stores = loadAll()
  const index = stores.findIndex((s) => s.id === id)
  if (index === -1) {
    throw new Error('店铺不存在')
  }
  const [removed] = stores.splice(index, 1)
  if (DEMO_STORES.some((s) => s.id === id)) {
    markDemoStoreRemoved(id)
  }
  saveAll(stores)
  syncOperationalDemoStores(stores)
  return { success: true, message: '店铺已解除绑定', data: removed }
}
