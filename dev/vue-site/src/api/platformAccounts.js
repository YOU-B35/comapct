import { useAuthStore } from '@/stores/auth'
import { hasBackendSession } from './backendSession'
import {
  bindBackendPlatformStore,
  bindBackendPlatformStoresBatch,
  deleteBackendPlatformStore,
  fetchBackendPlatformStores,
} from './platformAccountsApi'
import {
  bindLocalPlatformStoresBatch,
  deleteLocalPlatformStore,
  fetchLocalPlatformStores,
} from './platformAccountsLocal'
import { ensureAliexpressDemoData } from './aliexpressDemoLocal'
import { DTC_PLATFORMS } from '@/constants/platforms'
import { ensureDtcDemoData } from './dtcDemoLocal'
import { ensureDtcOrdersDemo } from './dtcOrdersLocal'
import { ensureAlibaba1688DemoData } from './alibaba1688DemoLocal'
import { ensureAmazonDailyData } from './amazonDailyLocal'
import { ensureAmazonBossData } from './amazonBossLocal'
import { fetchCachedWalmartOrders } from './walmartOrdersLocal'
import { fetchWalmartListingIssues } from './walmartListingsLocal'
import { loadCachedPddOrders, loadPddIssues, loadCachedDouyinOrders, loadDouyinIssues, loadCachedChannelsOrders, loadChannelsIssues, loadCachedTaobaoOrders, loadTaobaoIssues } from './domesticPlatforms'

function getAuth() {
  return useAuthStore()
}

export function canUsePlatformAccountsBackend(auth = getAuth()) {
  return hasBackendSession(auth)
}

async function fetchStores(platform) {
  if (canUsePlatformAccountsBackend()) {
    return await fetchBackendPlatformStores(platform)
  }
  return fetchLocalPlatformStores(platform)
}

export async function bindPlatformStore(payload) {
  if (canUsePlatformAccountsBackend()) {
    try {
      return await bindBackendPlatformStore(payload)
    } catch (err) {
      throw err
    }
  }
  return bindLocalPlatformStoresBatch({ companyName: payload.companyName, stores: [payload] })
}

export async function bindPlatformStoresBatch(payload) {
  if (canUsePlatformAccountsBackend()) {
    try {
      return await bindBackendPlatformStoresBatch(payload)
    } catch (err) {
      throw err
    }
  }
  return bindLocalPlatformStoresBatch(payload)
}

export function fetchPlatformStores(platform) {
  return fetchStores(platform)
}

/** 获取全部已绑定店铺（用于店铺编排） */
export function fetchAllPlatformStores() {
  return fetchStores()
}

export async function deletePlatformStore(id) {
  if (canUsePlatformAccountsBackend()) {
    try {
      return await deleteBackendPlatformStore(id)
    } catch (err) {
      throw err
    }
  }
  return deleteLocalPlatformStore(id)
}

/** 获取 AliExpress 运营已绑定的全部店铺 */
export async function fetchAliExpressStores() {
  const res = await fetchStores('aliexpress')
  if (!canUsePlatformAccountsBackend()) {
    ensureAliexpressDemoData(res.data || [])
  }
  return res
}

/** 获取 Walmart 运营已绑定的全部店铺 */
export async function fetchWalmartStores() {
  const res = await fetchStores('walmart')
  if (!canUsePlatformAccountsBackend() && res.data?.length) {
    fetchCachedWalmartOrders(res.data)
    fetchWalmartListingIssues(res.data)
  }
  return res
}

function ensureDomesticStoreData(stores, loadOrders, loadIssues) {
  if (stores?.length) {
    loadOrders(stores)
    loadIssues(stores)
  }
}

/** 获取拼多多运营已绑定的全部店铺 */
export async function fetchPddStores() {
  const res = await fetchStores('pdd')
  if (!canUsePlatformAccountsBackend()) {
    ensureDomesticStoreData(res.data, loadCachedPddOrders, loadPddIssues)
  }
  return res
}

/** 获取淘宝运营已绑定的全部店铺 */
export async function fetchTaobaoStores() {
  const res = await fetchStores('taobao')
  if (!canUsePlatformAccountsBackend()) {
    ensureDomesticStoreData(res.data, loadCachedTaobaoOrders, loadTaobaoIssues)
  }
  return res
}

/** 获取抖音运营已绑定的全部店铺 */
export async function fetchDouyinStores() {
  const res = await fetchStores('douyin')
  if (!canUsePlatformAccountsBackend()) {
    ensureDomesticStoreData(res.data, loadCachedDouyinOrders, loadDouyinIssues)
  }
  return res
}

/** 获取视频号运营已绑定的全部店铺 */
export async function fetchChannelsStores() {
  const res = await fetchStores('channels')
  if (!canUsePlatformAccountsBackend()) {
    ensureDomesticStoreData(res.data, loadCachedChannelsOrders, loadChannelsIssues)
  }
  return res
}

/** 获取 Amazon 运营已绑定的全部店铺 */
export async function fetchAmazonStores() {
  const res = await fetchStores('amazon')
  if (!canUsePlatformAccountsBackend()) {
    ensureAmazonDailyData(res.data || [])
    ensureAmazonBossData(res.data || [])
  }
  return res
}

/** 获取 1688 运营已绑定的全部店铺 */
export async function fetchAlibaba1688Stores() {
  const res = await fetchStores('1688')
  if (!canUsePlatformAccountsBackend()) {
    ensureAlibaba1688DemoData(res.data || [])
  }
  return res
}

/** 获取独立站运营已绑定的全部店铺（Shopify + WordPress） */
export async function fetchDtcStores() {
  const results = await Promise.all(DTC_PLATFORMS.map((platform) => fetchStores(platform)))
  const data = results.flatMap((res) => res.data || [])
  if (!canUsePlatformAccountsBackend()) {
    ensureDtcDemoData(data)
    ensureDtcOrdersDemo(data)
  }
  return {
    success: true,
    data,
  }
}
