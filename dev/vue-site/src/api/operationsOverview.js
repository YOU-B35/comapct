import { fetchPlatformStores, fetchAllPlatformStores, fetchAliExpressStores, fetchWalmartStores, fetchPddStores, fetchTaobaoStores, fetchDouyinStores, fetchChannelsStores, fetchAmazonStores, fetchAlibaba1688Stores, fetchDtcStores } from './platformAccounts'
import { canUseTemuBackend, fetchTemuOperationalData, fetchTemuStores } from './temuApi'
import { hasBackendSession } from './backendSession'
import { DTC_PLATFORMS } from '@/constants/platforms'
import { TEMU_PRODUCTS_RAW } from '@/constants/temu'
import { enrichAllProducts } from '@/utils/temu'
import { buildOperationsOverview } from '@/utils/operationsOverview'
import { buildPlatformSalesRows } from '@/utils/platformMetrics'
import { scopeStores } from '@/utils/scope'
import { getTemuRestockStatusMap } from './temuRestockLocal'
import { loadTemuRestockStatusMap } from './temuRestock'
import { loadCachedAliExpressOrders, loadAliExpressViolations } from './aliexpress'
import {
  canUseAliExpressBackend,
  fetchTodayAliExpressOrdersFromApi,
  loadAliExpressViolationsFromApi,
} from './aliexpressApi'
import { loadCachedWalmartOrders, loadWalmartListingIssues } from './walmart'
import { enrichListingIssue } from '@/utils/walmart'
import { enrichDomesticIssue } from '@/utils/domesticPlatform'
import { PDD_ISSUE_TYPES } from '@/constants/pddDemo'
import { TAOBAO_ISSUE_TYPES } from '@/constants/taobaoDemo'
import { DOUYIN_ISSUE_TYPES } from '@/constants/douyinDemo'
import { CHANNELS_ISSUE_TYPES } from '@/constants/channelsDemo'
import { loadCachedPddOrders, loadPddIssues, loadCachedTaobaoOrders, loadTaobaoIssues, loadCachedDouyinOrders, loadDouyinIssues, loadCachedChannelsOrders, loadChannelsIssues } from './domesticPlatforms'
import { canUseDouyinBackend, fetchDouyinOrdersToday } from './douyinApi'
import { ensureAliexpressDemoData } from './aliexpressDemoLocal'
import { loadAlibaba1688DemoData } from './alibaba1688DemoLocal'
import {
  canUseAlibaba1688Backend,
  fetchAlibaba1688Operational,
  fetchAlibaba1688OrderSummary,
  fetchAlibaba1688Products,
} from './alibaba1688Api'
import { filterItemsByStoreIds, enrichPurchaseOrder, enrichSupplierAlert } from '@/utils/alibaba1688'
import { isPlatformOperationalDemoOnly } from '@/utils/platformOperationalMode'
import { ensureAmazonDailyData } from './amazonDailyLocal'
import { loadAmazonDailyWorkflow } from './amazon'
import { fetchAmazonDailyFromBackend } from './amazonApi'
import { loadDtcTodayOrders, ensureDtcOrdersDemo } from './dtcOrdersLocal'
import { fetchEmployees } from './employees'
import { buildTaskCenterForAuth } from '@/utils/employeeTasks'
import { buildDailyOpsReport } from '@/utils/dailyOpsReport'
import { loadTodayOpsFeedback } from '@/api/opsFeedback'

function filterByStoreIds(items, storeIds) {
  const set = new Set(storeIds)
  return (items || []).filter((item) => set.has(item.storeId))
}

function normalizeDouyinOrder(row) {
  return {
    ...row,
    storeId: row.storeId || row.store_id || '',
    amount: Number(row.amount ?? row.pay_amount ?? row.payAmount ?? 0) || 0,
    status: row.status || row.order_status || row.orderStatus || '',
  }
}

/** 账户绑定店铺 + 爬虫 shop_id 合并，便于总览展示运营数据 */
function mergeTemuStoresForOverview(boundStores, products) {
  const stores = [...(boundStores || [])]
  const knownIds = new Set(stores.map((store) => store.id))
  for (const product of products || []) {
    if (!product.storeId || knownIds.has(product.storeId)) continue
    knownIds.add(product.storeId)
    stores.push({
      id: product.storeId,
      storeName: product.owner || product.storeId,
      platform: 'temu',
    })
  }
  return stores
}

async function loadTemuProducts(auth, boundStores) {
  if (canUseTemuBackend(auth) && boundStores.length) {
    try {
      const shopIds = boundStores
        .flatMap((store) => [store.externalShopId, store.id].filter(Boolean))
      const op = await fetchTemuOperationalData({})
      let products = op.products || []
      if (shopIds.length) {
        const allowed = new Set(shopIds)
        const filtered = products.filter((p) => allowed.has(p.storeId))
        products = filtered.length ? filtered : products
      }
      return products
    } catch {
      return []
    }
  }
  const temuStoreIds = boundStores.map((store) => store.id)
  return enrichAllProducts(filterByStoreIds(TEMU_PRODUCTS_RAW, temuStoreIds))
}

function filterStoresByPlatform(stores, platform) {
  const key = String(platform || '').toLowerCase()
  return (stores || []).filter((store) => String(store.platform || '').toLowerCase() === key)
}

async function loadBoundStoresByPlatform(auth) {
  const demoMode = !hasBackendSession(auth)
  if (!demoMode) {
    const res = await fetchAllPlatformStores()
    const all = scopeStores(res.data || [], auth)
    return {
      temu: await fetchTemuStores(auth),
      aliexpress: filterStoresByPlatform(all, 'aliexpress'),
      walmart: filterStoresByPlatform(all, 'walmart'),
      pdd: filterStoresByPlatform(all, 'pdd'),
      taobao: filterStoresByPlatform(all, 'taobao'),
      douyin: filterStoresByPlatform(all, 'douyin'),
      channels: filterStoresByPlatform(all, 'channels'),
      amazon: filterStoresByPlatform(all, 'amazon'),
      '1688': filterStoresByPlatform(all, '1688'),
      dtc: all.filter((store) => DTC_PLATFORMS.includes(String(store.platform || '').toLowerCase())),
    }
  }

  const [
    temuStoresRes,
    aeStoresRes,
    walmartStoresRes,
    pddStoresRes,
    taobaoStoresRes,
    douyinStoresRes,
    channelsStoresRes,
    amazonStoresRes,
    stores1688Res,
    dtcStoresRes,
  ] = await Promise.all([
    fetchPlatformStores('temu'),
    fetchAliExpressStores(),
    fetchWalmartStores(),
    fetchPddStores(),
    fetchTaobaoStores(),
    fetchDouyinStores(),
    fetchChannelsStores(),
    fetchAmazonStores(),
    fetchAlibaba1688Stores(),
    fetchDtcStores(),
  ])

  return {
    temu: scopeStores(temuStoresRes.data || [], auth),
    aliexpress: scopeStores(aeStoresRes.data || [], auth),
    walmart: scopeStores(walmartStoresRes.data || [], auth),
    pdd: scopeStores(pddStoresRes.data || [], auth),
    taobao: scopeStores(taobaoStoresRes.data || [], auth),
    douyin: scopeStores(douyinStoresRes.data || [], auth),
    channels: scopeStores(channelsStoresRes.data || [], auth),
    amazon: scopeStores(amazonStoresRes.data || [], auth),
    '1688': scopeStores(stores1688Res.data || [], auth),
    dtc: scopeStores(dtcStoresRes.data || [], auth),
  }
}

/** 统一运营上下文：账户绑定 → 店铺 → 员工 → 各平台运营数据 → 总览 */
export async function loadOperationsOverview(auth = null) {
  const [storeMap, employeesRes] = await Promise.all([
    loadBoundStoresByPlatform(auth),
    fetchEmployees(auth),
  ])

  const employees = employeesRes.data || []
  const demoMode = !hasBackendSession(auth)
  let temuStores = storeMap.temu || []
  let temuProducts = await loadTemuProducts(auth, temuStores)
  if (canUseTemuBackend(auth)) {
    temuStores = mergeTemuStoresForOverview(temuStores, temuProducts)
  }
  const aeStores = storeMap.aliexpress || []
  const walmartStores = storeMap.walmart || []
  const pddStores = storeMap.pdd || []
  const taobaoStores = storeMap.taobao || []
  const douyinStores = storeMap.douyin || []
  const channelsStores = storeMap.channels || []
  const amazonStores = storeMap.amazon || []
  const stores1688 = storeMap['1688'] || []
  const dtcStores = storeMap.dtc || []

  const temuStoreIds = temuStores.map((store) => store.id)
  const aeStoreIds = aeStores.map((store) => store.id)
  const walmartStoreIds = walmartStores.map((store) => store.id)
  const pddStoreIds = pddStores.map((store) => store.id)
  const taobaoStoreIds = taobaoStores.map((store) => store.id)
  const douyinStoreIds = douyinStores.map((store) => store.id)
  const channelsStoreIds = channelsStores.map((store) => store.id)
  const amazonStoreIds = amazonStores.map((store) => store.id)
  const stores1688Ids = stores1688.map((store) => store.id)
  const dtcStoreIds = dtcStores.map((store) => store.id)

  const temuProductsFinal = temuProducts
  const temuRestockStatus = demoMode
    ? getTemuRestockStatusMap()
    : await loadTemuRestockStatusMap(auth)

  if (demoMode && dtcStores.length) {
    ensureDtcOrdersDemo(dtcStores)
  }

  if (demoMode && aeStores.length) {
    ensureAliexpressDemoData(aeStores)
  }

  if (demoMode && amazonStores.length) {
    ensureAmazonDailyData(amazonStores)
  }

  const aeOrders = demoMode && aeStores.length
    ? filterByStoreIds(loadCachedAliExpressOrders(aeStores).data.orders, aeStoreIds)
    : canUseAliExpressBackend(auth) && aeStores.length
      ? filterByStoreIds((await fetchTodayAliExpressOrdersFromApi()).orders || [], aeStoreIds)
      : []
  const aeViolations = demoMode && aeStores.length
    ? filterByStoreIds((await loadAliExpressViolations(aeStores, auth)).data.violations, aeStoreIds)
    : canUseAliExpressBackend(auth) && aeStores.length
      ? filterByStoreIds((await loadAliExpressViolationsFromApi()).violations || [], aeStoreIds)
      : []

  const wmOrders = demoMode && walmartStores.length
    ? filterByStoreIds(loadCachedWalmartOrders(walmartStores).data.orders, walmartStoreIds)
    : []
  const wmIssues = demoMode && walmartStores.length
    ? filterByStoreIds(
        loadWalmartListingIssues(walmartStores).data.issues.map((issue) => enrichListingIssue(issue)),
        walmartStoreIds,
      )
    : []

  const pddOrders = demoMode && pddStores.length
    ? filterByStoreIds(loadCachedPddOrders(pddStores).data.orders, pddStoreIds)
    : []
  const pddIssues = demoMode && pddStores.length
    ? filterByStoreIds(
        loadPddIssues(pddStores).data.issues.map((issue) => enrichDomesticIssue(issue, PDD_ISSUE_TYPES)),
        pddStoreIds,
      )
    : []

  const taobaoOrders = demoMode && taobaoStores.length
    ? filterByStoreIds(loadCachedTaobaoOrders(taobaoStores).data.orders, taobaoStoreIds)
    : []
  const taobaoIssues = demoMode && taobaoStores.length
    ? filterByStoreIds(
        loadTaobaoIssues(taobaoStores).data.issues.map((issue) => enrichDomesticIssue(issue, TAOBAO_ISSUE_TYPES)),
        taobaoStoreIds,
      )
    : []

  let douyinOrders = []
  let douyinIssues = []
  if (demoMode && douyinStores.length) {
    douyinOrders = filterItemsByStoreIds(
      (loadCachedDouyinOrders(douyinStores).data.orders || []).map(normalizeDouyinOrder),
      douyinStoreIds,
    )
    const douyinIssuesRes = await loadDouyinIssues(douyinStores)
    douyinIssues = filterItemsByStoreIds(
      (douyinIssuesRes?.data?.issues || []).map((issue) => enrichDomesticIssue(issue, DOUYIN_ISSUE_TYPES)),
      douyinStoreIds,
    )
  } else if (canUseDouyinBackend(auth) && douyinStores.length) {
    try {
      const data = await fetchDouyinOrdersToday()
      douyinOrders = filterItemsByStoreIds(
        (data.items || []).map(normalizeDouyinOrder),
        douyinStoreIds,
      )
    } catch {
      douyinOrders = []
    }
    try {
      const douyinIssuesRes = await loadDouyinIssues(douyinStores)
      douyinIssues = filterItemsByStoreIds(
        (douyinIssuesRes?.data?.issues || []).map((issue) => enrichDomesticIssue(issue, DOUYIN_ISSUE_TYPES)),
        douyinStoreIds,
      )
    } catch {
      douyinIssues = []
    }
  }

  const channelsOrders = demoMode && channelsStores.length
    ? filterByStoreIds(loadCachedChannelsOrders(channelsStores).data.orders, channelsStoreIds)
    : []
  const channelsIssues = demoMode && channelsStores.length
    ? filterByStoreIds(
        loadChannelsIssues(channelsStores).data.issues.map((issue) => enrichDomesticIssue(issue, CHANNELS_ISSUE_TYPES)),
        channelsStoreIds,
      )
    : []

  const amazonDaily = demoMode && amazonStores.length
    ? (await loadAmazonDailyWorkflow(amazonStores)).data
    : hasBackendSession(auth) && amazonStores.length
      ? (await fetchAmazonDailyFromBackend(amazonStores)).data
      : {
          buyerMessages: [],
          accountMetrics: [],
          reviews: [],
          coupons: [],
          sellerNews: [],
          shipments: [],
          cases: [],
        }

  let purchaseOrders = []
  let supplierAlerts = []
  let products1688 = []
  let summary1688 = null
  const use1688Backend =
    !demoMode &&
    stores1688.length > 0 &&
    canUseAlibaba1688Backend(auth) &&
    !isPlatformOperationalDemoOnly('1688')
  if (use1688Backend) {
    try {
      const op = await fetchAlibaba1688Operational()
      purchaseOrders = filterItemsByStoreIds(
        (op.purchaseOrders || []).map(enrichPurchaseOrder),
        stores1688Ids,
      )
      supplierAlerts = filterItemsByStoreIds(
        (op.supplierAlerts || []).map(enrichSupplierAlert),
        stores1688Ids,
      )
    } catch {
      purchaseOrders = []
      supplierAlerts = []
    }
    try {
      const prod = await fetchAlibaba1688Products({ tab: 'all', status: 'all' })
      products1688 = filterItemsByStoreIds(prod.items || [], stores1688Ids)
    } catch {
      products1688 = []
    }
    try {
      const today = new Date()
      const dateText = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
      const data = await fetchAlibaba1688OrderSummary({ startDate: dateText, endDate: dateText })
      summary1688 = data || null
    } catch {
      summary1688 = null
    }
  } else if (demoMode && stores1688.length) {
    const demo1688 = loadAlibaba1688DemoData(stores1688)
    purchaseOrders = filterItemsByStoreIds(demo1688.purchaseOrders, stores1688Ids)
    supplierAlerts = filterItemsByStoreIds(demo1688.supplierAlerts, stores1688Ids)
    products1688 = []
  }

  const dtcOrders = demoMode ? filterByStoreIds(loadDtcTodayOrders(dtcStores), dtcStoreIds) : []

  const temuPayload = {
    stores: temuStores,
    products: temuProductsFinal,
    restockStatus: temuRestockStatus,
  }
  const aliexpressPayload = {
    stores: aeStores,
    orders: aeOrders,
    violations: aeViolations,
  }
  const walmartPayload = {
    stores: walmartStores,
    orders: wmOrders,
    issues: wmIssues,
  }
  const pddPayload = {
    stores: pddStores,
    orders: pddOrders,
    issues: pddIssues,
  }
  const taobaoPayload = {
    stores: taobaoStores,
    orders: taobaoOrders,
    issues: taobaoIssues,
  }
  const douyinPayload = {
    stores: douyinStores,
    orders: douyinOrders,
    issues: douyinIssues,
  }
  const channelsPayload = {
    stores: channelsStores,
    orders: channelsOrders,
    issues: channelsIssues,
  }
  const amazonPayload = {
    stores: amazonStores,
    buyerMessages: filterByStoreIds(amazonDaily.buyerMessages, amazonStoreIds),
    accountMetrics: filterByStoreIds(amazonDaily.accountMetrics, amazonStoreIds),
    reviews: filterByStoreIds(amazonDaily.reviews, amazonStoreIds),
    coupons: filterByStoreIds(amazonDaily.coupons, amazonStoreIds),
    sellerNews: filterByStoreIds(amazonDaily.sellerNews, amazonStoreIds),
    shipments: filterByStoreIds(amazonDaily.shipments, amazonStoreIds),
    cases: filterByStoreIds(amazonDaily.cases, amazonStoreIds),
  }
  const alibaba1688Payload = {
    stores: stores1688,
    purchaseOrders,
    supplierAlerts,
    products: products1688,
    summary: summary1688,
  }
  const dtcPayload = {
    stores: dtcStores,
    orders: dtcOrders,
  }

  const storeNameMaps = {
    temu: Object.fromEntries(temuStores.map((store) => [store.id, store.storeName])),
    aliexpress: Object.fromEntries(aeStores.map((store) => [store.id, store.storeName])),
    walmart: Object.fromEntries(walmartStores.map((store) => [store.id, store.storeName])),
    pdd: Object.fromEntries(pddStores.map((store) => [store.id, store.storeName])),
    taobao: Object.fromEntries(taobaoStores.map((store) => [store.id, store.storeName])),
    douyin: Object.fromEntries(douyinStores.map((store) => [store.id, store.storeName])),
    channels: Object.fromEntries(channelsStores.map((store) => [store.id, store.storeName])),
    amazon: Object.fromEntries(amazonStores.map((store) => [store.id, store.storeName])),
    '1688': Object.fromEntries(stores1688.map((store) => [store.id, store.storeName])),
    dtc: Object.fromEntries(dtcStores.map((store) => [store.id, store.storeName])),
  }

  const overview = buildOperationsOverview({
    temu: temuPayload,
    aliexpress: aliexpressPayload,
    walmart: walmartPayload,
    pdd: pddPayload,
    taobao: taobaoPayload,
    douyin: douyinPayload,
    channels: channelsPayload,
    amazon: amazonPayload,
    alibaba1688: alibaba1688Payload,
    dtc: dtcPayload,
    storeNameMaps,
    employees,
  })

  const platformSales = buildPlatformSalesRows({
    temu: temuPayload,
    aliexpress: aliexpressPayload,
    walmart: walmartPayload,
    pdd: pddPayload,
    taobao: taobaoPayload,
    douyin: douyinPayload,
    channels: channelsPayload,
    amazon: amazonPayload,
    alibaba1688: alibaba1688Payload,
    dtc: dtcPayload,
    employees,
  })

  const tasks = await buildTaskCenterForAuth(
    { platforms: overview.platforms, totalIssues: overview.totalIssues, syncedAt: overview.syncedAt },
    auth,
    employees,
  ).catch(() => [])

  const feedbacksRes = await loadTodayOpsFeedback({}, auth).catch(() => ({ data: [] }))
  const feedbacks = feedbacksRes.data || []
  const dailyReport = auth?.isBoss
    ? buildDailyOpsReport({
        overview,
        platformSales,
        employees,
        tasks,
        feedbacks,
      })
    : null

  return {
    success: true,
    data: {
      ...overview,
      platformSales,
      tasks,
      employees,
      feedbacks,
      dailyReport,
      stores: {
        temu: temuStores,
        aliexpress: aeStores,
        walmart: walmartStores,
        pdd: pddStores,
        taobao: taobaoStores,
        douyin: douyinStores,
        channels: channelsStores,
        amazon: amazonStores,
        '1688': stores1688,
        dtc: dtcStores,
      },
    },
  }
}
